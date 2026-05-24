import { invoke } from "@tauri-apps/api/core";
import { useRef } from "react";
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

function splitIntoSentences(text: string): string[] {
  return text
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 3);
}

export function useTTS() {
  const { setIsSpeaking } = useStore();
  const audioCtxRef = useRef<AudioContext | null>(null);
  const sourcesRef = useRef<AudioBufferSourceNode[]>([]);

  const cancel = () => {
    const ctx = audioCtxRef.current;
    audioCtxRef.current = null;
    sourcesRef.current.forEach((s) => {
      try {
        s.stop();
      } catch {}
    });
    sourcesRef.current = [];
    if (ctx) ctx.close();
    setIsSpeaking(false);
  };

  const speak = async (text: string) => {
    if (!text.trim()) return;

    cancel();

    const cleanText = stripMarkdown(text);
    const sentences = splitIntoSentences(cleanText);
    if (sentences.length === 0) return;

    setIsSpeaking(true);
    const audioCtx = new AudioContext();
    audioCtxRef.current = audioCtx;
    sourcesRef.current = [];

    // Tous les fetches démarrent en parallèle
    const fetchPromises = sentences.map((s) =>
      invoke<number[]>("synthesize_speech", { text: s })
    );

    let playbackEndTime = audioCtx.currentTime;

    try {
      for (let i = 0; i < fetchPromises.length; i++) {
        const bytes = await fetchPromises[i];
        if (audioCtxRef.current !== audioCtx) return; // annulé pendant l'attente

        const buffer = await audioCtx.decodeAudioData(
          new Uint8Array(bytes).buffer
        );
        const source = audioCtx.createBufferSource();
        source.buffer = buffer;
        source.connect(audioCtx.destination);
        sourcesRef.current.push(source);

        const startAt = Math.max(audioCtx.currentTime, playbackEndTime);
        source.start(startAt);
        playbackEndTime = startAt + buffer.duration;

        if (i === fetchPromises.length - 1) {
          source.onended = () => {
            if (audioCtxRef.current === audioCtx) {
              setIsSpeaking(false);
              audioCtx.close();
              audioCtxRef.current = null;
            }
          };
        }
      }
    } catch (err) {
      console.error("TTS error:", err);
      cancel();
    }
  };

  return { speak, cancel };
}
