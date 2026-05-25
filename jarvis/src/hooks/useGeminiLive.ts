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
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/^[-*+]\s+/gm, "")
    .replace(/^\d+\.\s+/gm, "")
    .replace(/^>\s*/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function useGeminiLive() {
  // ── Recording refs ──────────────────────────────────────────────────────────
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const micCtxRef        = useRef<AudioContext | null>(null);
  const analyserRef      = useRef<AnalyserNode | null>(null);
  const animFrameRef     = useRef<number>(0);
  const chunksRef        = useRef<Blob[]>([]);
  const activeRef        = useRef(false);

  // ── TTS refs ────────────────────────────────────────────────────────────────
  const ttsCtxRef          = useRef<AudioContext | null>(null);
  const sourcesRef         = useRef<AudioBufferSourceNode[]>([]);
  const playbackEndTimeRef = useRef<number>(0);
  const scheduleChainRef   = useRef<Promise<void>>(Promise.resolve());

  const {
    setIsListening, setIsThinking, setIsSpeaking,
    addMessage, setAudioLevel,
    memoryContext, messages,
  } = useStore();

  // ── TTS ─────────────────────────────────────────────────────────────────────
  const cancelTTS = useCallback(() => {
    const ctx = ttsCtxRef.current;
    ttsCtxRef.current = null;
    scheduleChainRef.current = Promise.resolve();
    sourcesRef.current.forEach((s) => { try { s.stop(); } catch {} });
    sourcesRef.current = [];
    if (ctx) ctx.close();
    setIsSpeaking(false);
  }, [setIsSpeaking]);

  const speakSentence = useCallback((sentence: string) => {
    const clean = stripMarkdown(sentence).trim();
    if (clean.length <= 3) return;

    if (!ttsCtxRef.current) {
      const ctx = new AudioContext();
      ttsCtxRef.current = ctx;
      sourcesRef.current = [];
      playbackEndTimeRef.current = ctx.currentTime;
      scheduleChainRef.current = Promise.resolve();
      setIsSpeaking(true);
    }

    const audioCtx = ttsCtxRef.current;
    // Fire TTS fetch immediately, schedule playback in order via chain
    const fetchPromise = invoke<number[]>("synthesize_speech", { text: clean });

    scheduleChainRef.current = scheduleChainRef.current.then(async () => {
      if (ttsCtxRef.current !== audioCtx) return; // cancelled
      try {
        const bytes = await fetchPromise;
        if (ttsCtxRef.current !== audioCtx) return;
        const buffer = await audioCtx.decodeAudioData(new Uint8Array(bytes).buffer);
        const source = audioCtx.createBufferSource();
        source.buffer = buffer;
        source.connect(audioCtx.destination);
        sourcesRef.current.push(source);
        const startAt = Math.max(audioCtx.currentTime, playbackEndTimeRef.current);
        source.start(startAt);
        playbackEndTimeRef.current = startAt + buffer.duration;
      } catch (err) {
        console.error("[jarvis] TTS sentence error:", err);
      }
    });
  }, [setIsSpeaking]);

  const finishSpeaking = useCallback(() => {
    const audioCtx = ttsCtxRef.current;
    if (!audioCtx) return;

    scheduleChainRef.current.then(() => {
      if (ttsCtxRef.current !== audioCtx) return;
      const sources = sourcesRef.current;
      const cleanup = () => {
        if (ttsCtxRef.current === audioCtx) {
          setIsSpeaking(false);
          audioCtx.close();
          ttsCtxRef.current = null;
        }
      };
      if (sources.length === 0 || audioCtx.currentTime >= playbackEndTimeRef.current) {
        cleanup();
        return;
      }
      sources[sources.length - 1].onended = cleanup;
    });
  }, [setIsSpeaking]);

  // TTS event listeners (stable — deps are zustand setters)
  useEffect(() => {
    const p1 = listen<string>("claude-sentence", (e) => speakSentence(e.payload));
    const p2 = listen<void>("claude-done", () => finishSpeaking());
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

        await invoke("ask_claude", { messages: history, systemPrompt });
      } catch (err) {
        console.error("[jarvis] useGeminiLive error:", err);
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

  // Spacebar binding
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.code === "Space" && !e.repeat && !(e.target as HTMLElement)?.matches("input,textarea")) {
        e.preventDefault();
        startListening();
      }
    };
    const up = (e: KeyboardEvent) => {
      if (e.code === "Space") stopListening();
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [startListening, stopListening]);

  return { startListening, stopListening };
}
