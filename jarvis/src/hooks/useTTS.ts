import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { useEffect, useRef } from "react";
import { useStore } from "../store";

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

export function useTTS() {
  const { setIsSpeaking } = useStore();
  const audioCtxRef        = useRef<AudioContext | null>(null);
  const sourcesRef         = useRef<AudioBufferSourceNode[]>([]);
  const playbackEndTimeRef = useRef<number>(0);
  // Chain ensures sentences are scheduled in arrival order despite parallel fetches
  const scheduleChainRef   = useRef<Promise<void>>(Promise.resolve());

  const cancel = () => {
    const ctx = audioCtxRef.current;
    audioCtxRef.current = null;
    scheduleChainRef.current = Promise.resolve();
    sourcesRef.current.forEach((s) => {
      try { s.stop(); } catch {}
    });
    sourcesRef.current = [];
    if (ctx) ctx.close();
    setIsSpeaking(false);
  };

  const speakSentence = (sentence: string) => {
    const clean = stripMarkdown(sentence).trim();
    if (clean.length <= 3) return;

    // Initialize AudioContext on the first sentence of a new response
    if (!audioCtxRef.current) {
      const ctx = new AudioContext();
      audioCtxRef.current = ctx;
      sourcesRef.current = [];
      playbackEndTimeRef.current = ctx.currentTime;
      scheduleChainRef.current = Promise.resolve();
      setIsSpeaking(true);
    }

    const audioCtx = audioCtxRef.current;

    // Launch ElevenLabs fetch immediately — runs in parallel with other sentences
    const fetchPromise = invoke<number[]>("synthesize_speech", { text: clean });

    // Chain scheduling so sentences play in order regardless of fetch latency
    scheduleChainRef.current = scheduleChainRef.current.then(async () => {
      if (audioCtxRef.current !== audioCtx) return; // cancelled
      try {
        const bytes = await fetchPromise;
        if (audioCtxRef.current !== audioCtx) return;
        const buffer = await audioCtx.decodeAudioData(new Uint8Array(bytes).buffer);
        const source = audioCtx.createBufferSource();
        source.buffer = buffer;
        source.connect(audioCtx.destination);
        sourcesRef.current.push(source);
        const startAt = Math.max(audioCtx.currentTime, playbackEndTimeRef.current);
        source.start(startAt);
        playbackEndTimeRef.current = startAt + buffer.duration;
      } catch (err) {
        console.error("TTS sentence error:", err);
      }
    });
  };

  // Called by useClaudeStream on claude-done to attach cleanup to last source
  const finishSpeaking = () => {
    const audioCtx = audioCtxRef.current;
    if (!audioCtx) return;

    scheduleChainRef.current.then(() => {
      if (audioCtxRef.current !== audioCtx) return;
      const sources = sourcesRef.current;

      const cleanup = () => {
        if (audioCtxRef.current === audioCtx) {
          setIsSpeaking(false);
          audioCtx.close();
          audioCtxRef.current = null;
        }
      };

      if (sources.length === 0 || audioCtx.currentTime >= playbackEndTimeRef.current) {
        cleanup();
        return;
      }
      sources[sources.length - 1].onended = cleanup;
    });
  };

  // Enqueue each sentence the moment Rust detects a boundary
  useEffect(() => {
    const unsub = listen<string>("claude-sentence", (e) => {
      speakSentence(e.payload);
    });
    return () => { unsub.then((fn) => fn()); };
  }, []);

  return { cancel, finishSpeaking };
}
