import { useCallback, useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { useStore } from "../store";
import type { Message } from "../types";

function buildSystemPrompt(soul: string, user: string, memory: string): string {
  return `Tu es le compagnon IA personnel de l'utilisateur.

<SOUL>
${soul}
</SOUL>

<USER>
${user}
</USER>

<MEMORY>
${memory}
</MEMORY>

Règles absolues :
- Réponds toujours en français
- Sois direct, dense, sans fioritures
- Ne valide pas pour faire plaisir — dis ce que tu vois
- Une question à la fois maximum`;
}


function stripMarkdown(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, "")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/_([^_]+)_/g, "$1")
    .replace(/~~([^~]+)~~/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/^[-*+]\s+/gm, "")
    .replace(/^\d+\.\s+/gm, "")
    .replace(/^>\s*/gm, "")
    .replace(/^\s*[-*_]{3,}\s*$/gm, "")
    .replace(/\|[^\n|]*\|/g, "")
    .replace(/&[a-zA-Z]+;|&#\d+;/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function useGeminiLive() {
  // ── Recording refs ──────────────────────────────────────────────────────────
  const mediaRecorderRef  = useRef<MediaRecorder | null>(null);
  const micCtxRef         = useRef<AudioContext | null>(null);
  const analyserRef       = useRef<AnalyserNode | null>(null);
  const animFrameRef      = useRef<number>(0);
  const chunksRef         = useRef<Blob[]>([]);
  const activeRef         = useRef(false);
  const sttTimerActiveRef = useRef(false);

  // ── TTS refs ────────────────────────────────────────────────────────────────
  // AudioContext is created once and kept alive for the component lifetime.
  // Per-turn state is managed via ttsIdleRef + turnIdRef rather than
  // close/recreate, which avoids currentTime resets and scheduling races.
  const ttsCtxRef          = useRef<AudioContext | null>(null);
  const ttsAnalyserRef     = useRef<AnalyserNode | null>(null);
  const ttsRafRef          = useRef<number>(0);
  const sourcesRef         = useRef<AudioBufferSourceNode[]>([]);
  const playbackEndTimeRef = useRef<number>(0);
  const scheduleChainRef   = useRef<Promise<void>>(Promise.resolve());
  const ttsIdleRef          = useRef(true);   // true = between turns, false = playing
  const turnIdRef           = useRef(0);      // incremented on cancel; chain handlers capture it
  const acceptSentencesRef  = useRef(false);  // true only while current ask_claude is streaming

  const {
    setIsListening, setIsThinking, setIsSpeaking,
    addMessage, setAudioLevel,
    memoryContext, messages,
  } = useStore();

  // ── TTS ─────────────────────────────────────────────────────────────────────
  const cancelTTS = useCallback(() => {
    cancelAnimationFrame(ttsRafRef.current);
    setAudioLevel(0);
    scheduleChainRef.current = Promise.resolve();
    sourcesRef.current.forEach((s) => { try { s.stop(); } catch {} });
    sourcesRef.current = [];
    turnIdRef.current++;
    ttsIdleRef.current = true;
    acceptSentencesRef.current = false;
    setIsSpeaking(false);
    // AudioContext stays open — currentTime keeps advancing, no scheduling reset.
  }, [setIsSpeaking, setAudioLevel]);

  const speakSentence = useCallback((sentence: string) => {
    const clean = stripMarkdown(sentence).trim();
    console.log("[jarvis] speakSentence: appelé —", JSON.stringify(clean.slice(0, 60)), `(${clean.length} chars)`);
    if (clean.length <= 3) {
      console.log("[jarvis] speakSentence: trop court, ignoré");
      return;
    }
    if (!/[a-zA-ZÀ-ÿ0-9]/.test(clean)) {
      console.log("[jarvis] speakSentence: aucun contenu lisible, ignoré");
      return;
    }

    // Create AudioContext exactly once for the lifetime of this hook instance.
    if (!ttsCtxRef.current) {
      const ctx = new AudioContext();
      console.log("[jarvis] speakSentence: AudioContext créé — state:", ctx.state);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyser.connect(ctx.destination);
      ttsAnalyserRef.current = analyser;
      ttsCtxRef.current = ctx;
    }

    const audioCtx = ttsCtxRef.current;

    // First sentence of a new turn: anchor the schedule to now so there is no
    // gap caused by playbackEndTimeRef holding a value from a previous turn.
    if (ttsIdleRef.current) {
      ttsIdleRef.current = false;
      sourcesRef.current = [];
      scheduleChainRef.current = Promise.resolve();
      playbackEndTimeRef.current = audioCtx.currentTime;
      console.log("[jarvis] speakSentence: nouveau tour — playbackEnd ancré à", audioCtx.currentTime.toFixed(3));
      setIsSpeaking(true);

      const myLoop = turnIdRef.current;
      const freqData = new Uint8Array(ttsAnalyserRef.current!.frequencyBinCount);
      const meterLoop = () => {
        if (turnIdRef.current !== myLoop) { setAudioLevel(0); return; }
        ttsAnalyserRef.current!.getByteFrequencyData(freqData);
        let sum = 0;
        for (let i = 0; i < freqData.length; i++) sum += freqData[i];
        setAudioLevel(sum / freqData.length / 255);
        ttsRafRef.current = requestAnimationFrame(meterLoop);
      };
      ttsRafRef.current = requestAnimationFrame(meterLoop);
    }

    // Capture turn identity so the async chain can detect cancellation.
    const myTurnId = turnIdRef.current;
    console.log("[jarvis] speakSentence: invoke synthesize_speech →", JSON.stringify(clean.slice(0, 60)));
    const fetchPromise = invoke<number[]>("synthesize_speech", { text: clean });

    scheduleChainRef.current = scheduleChainRef.current.then(async () => {
      if (turnIdRef.current !== myTurnId) {
        console.log("[jarvis] speakSentence: tour annulé, abandon");
        return;
      }
      try {
        const bytes = await fetchPromise;
        console.log("[jarvis] speakSentence: synthesize_speech retourné —", bytes.length, "bytes MP3");
        if (turnIdRef.current !== myTurnId) return;
        if (bytes.length === 0) {
          console.error("[jarvis] speakSentence: 0 bytes reçus — pas d'audio");
          return;
        }
        const mp3Buf = new Uint8Array(bytes).buffer;
        console.log("[jarvis] speakSentence: decodeAudioData sur MP3", mp3Buf.byteLength, "bytes, ctx.state=", audioCtx.state);
        const buffer = await audioCtx.decodeAudioData(mp3Buf);
        console.log("[jarvis] speakSentence: audio décodé — duration:", buffer.duration.toFixed(2), "s, sampleRate:", buffer.sampleRate);
        if (turnIdRef.current !== myTurnId) return;
        const source = audioCtx.createBufferSource();
        source.buffer = buffer;
        source.connect(ttsAnalyserRef.current ?? audioCtx.destination);
        // First source of a turn always starts now — never use a stale playbackEndTimeRef.
        const isFirst = sourcesRef.current.length === 0;
        sourcesRef.current.push(source);
        const startAt = isFirst
          ? audioCtx.currentTime
          : Math.max(audioCtx.currentTime, playbackEndTimeRef.current);
        source.start(startAt);
        playbackEndTimeRef.current = startAt + buffer.duration;
        console.log("[jarvis] speakSentence: source.start(", startAt.toFixed(3), ") isFirst=", isFirst, "ctx.now=", audioCtx.currentTime.toFixed(3), "— fin prévue à", playbackEndTimeRef.current.toFixed(3));
      } catch (err) {
        console.error("[jarvis] speakSentence: ERREUR —", err);
      }
    });
  }, [setIsSpeaking, setAudioLevel]);

  const finishSpeaking = useCallback(() => {
    const audioCtx = ttsCtxRef.current;
    const myTurnId = turnIdRef.current;
    console.log("[jarvis] finishSpeaking: appelé — audioCtx présent:", !!audioCtx);
    if (!audioCtx) return;

    scheduleChainRef.current.then(() => {
      if (turnIdRef.current !== myTurnId) return;
      const sources = sourcesRef.current;
      const cleanup = () => {
        if (turnIdRef.current !== myTurnId) return;
        cancelAnimationFrame(ttsRafRef.current);
        setAudioLevel(0);
        ttsIdleRef.current = true;
        setIsSpeaking(false);
        // AudioContext stays open.
      };
      if (sources.length === 0 || audioCtx.currentTime >= playbackEndTimeRef.current) {
        cleanup();
        return;
      }
      sources[sources.length - 1].onended = cleanup;
    });
  }, [setIsSpeaking, setAudioLevel]);

  // TTS event listeners (stable — deps are zustand setters)
  useEffect(() => {
    const p1 = listen<string>("claude-sentence", (e) => {
      if (!acceptSentencesRef.current) {
        console.log("[jarvis] claude-sentence ignoré (stale — ask_claude précédent)");
        return;
      }
      if (sttTimerActiveRef.current) {
        console.timeEnd("stt→claude");
        sttTimerActiveRef.current = false;
      }
      console.log("[jarvis] claude-sentence reçu:", JSON.stringify(e.payload.slice(0, 60)));
      speakSentence(e.payload);
    });
    const p2 = listen<void>("claude-done", () => {
      if (!acceptSentencesRef.current) return;
      acceptSentencesRef.current = false;
      console.log("[jarvis] claude-done reçu → finishSpeaking");
      finishSpeaking();
    });
    return () => {
      p1.then((fn) => fn());
      p2.then((fn) => fn());
    };
  }, [speakSentence, finishSpeaking]);

  // ── Recording ────────────────────────────────────────────────────────────────
  const stopListening = useCallback(() => {
    if (!activeRef.current) return;
    activeRef.current = false;
    mediaRecorderRef.current?.stop();
    setIsListening(false);
  }, [setIsListening]);

  const startListening = useCallback(async () => {
    if (activeRef.current) return;
    activeRef.current = true;
    cancelTTS();

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      activeRef.current = false;
      return;
    }

    micCtxRef.current = new AudioContext();
    analyserRef.current = micCtxRef.current.createAnalyser();
    analyserRef.current.fftSize = 256;
    micCtxRef.current.createMediaStreamSource(stream).connect(analyserRef.current);

    const data = new Uint8Array(analyserRef.current.frequencyBinCount);
    const tick = () => {
      analyserRef.current!.getByteFrequencyData(data);
      const avg = data.reduce((a, b) => a + b, 0) / data.length;
      setAudioLevel(avg / 255);
      animFrameRef.current = requestAnimationFrame(tick);
    };
    tick();

    chunksRef.current = [];
    const mr = new MediaRecorder(stream);
    mediaRecorderRef.current = mr;

    mr.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };

    mr.onstop = async () => {
      cancelAnimationFrame(animFrameRef.current);
      setAudioLevel(0);
      stream.getTracks().forEach((t) => t.stop());
      micCtxRef.current?.close();

      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      if (blob.size < 1000) return;

      const buf = await blob.arrayBuffer();
      const audioData = Array.from(new Uint8Array(buf));

      setIsThinking(true);
      try {
        const transcript = await invoke<string>("transcribe_gemini", { audioData });
        if (!transcript.trim()) {
          setIsThinking(false);
          return;
        }
        sttTimerActiveRef.current = true;
        console.time("stt→claude");

        const userMsg: Message = {
          id: `${Date.now()}-u`,
          role: "user",
          content: transcript.trim(),
          timestamp: Date.now(),
        };
        addMessage(userMsg);

        const history = [...messages, userMsg].map((m) => ({
          role: m.role,
          content: m.content,
        }));

        const systemPrompt = memoryContext
          ? buildSystemPrompt(memoryContext.soul, memoryContext.user, memoryContext.memory)
          : "Tu es un assistant personnel. Réponds en français.";

        acceptSentencesRef.current = true;
        await invoke("ask_claude", { messages: history, systemPrompt });
      } catch (err) {
        console.error("[jarvis] useGeminiLive error:", err);
        acceptSentencesRef.current = false;
        setIsThinking(false);
      }
    };

    mr.start();
    setIsListening(true);
  }, [memoryContext, messages, cancelTTS, setIsListening, setIsThinking, setAudioLevel, addMessage]);

  // Warm-up : prime le codec MediaRecorder au montage
  useEffect(() => {
    let cancelled = false;
    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((stream) => {
        if (cancelled) { stream.getTracks().forEach((t) => t.stop()); return; }
        const mr = new MediaRecorder(stream);
        mr.onstop = () => stream.getTracks().forEach((t) => t.stop());
        mr.start();
        mr.stop();
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  return { startListening, stopListening };
}
