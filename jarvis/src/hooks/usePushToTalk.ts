import { useEffect, useRef, useCallback } from "react";
import { invoke } from "@tauri-apps/api/core";
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

export function usePushToTalk() {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioCtxRef      = useRef<AudioContext | null>(null);
  const analyserRef      = useRef<AnalyserNode | null>(null);
  const animFrameRef     = useRef<number>(0);
  const chunksRef        = useRef<Blob[]>([]);
  const activeRef        = useRef(false);

  const {
    setIsListening, setIsThinking, addMessage, setAudioLevel,
    memoryContext, messages,
  } = useStore();

  const stopListening = useCallback(() => {
    if (!activeRef.current) return;
    activeRef.current = false;
    mediaRecorderRef.current?.stop();
    setIsListening(false);
  }, []);

  const startListening = useCallback(async () => {
    if (activeRef.current) return;
    activeRef.current = true;

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      activeRef.current = false;
      return;
    }

    // Audio level analysis
    audioCtxRef.current = new AudioContext();
    analyserRef.current = audioCtxRef.current.createAnalyser();
    analyserRef.current.fftSize = 256;
    audioCtxRef.current.createMediaStreamSource(stream).connect(analyserRef.current);

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
      audioCtxRef.current?.close();

      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      if (blob.size < 1000) return; // too short

      const buf = await blob.arrayBuffer();
      const audioData = Array.from(new Uint8Array(buf));

      setIsThinking(true);
      try {
        const transcript = await invoke<string>("transcribe_audio", { audioData });
        if (!transcript.trim()) return;

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
        console.error("push-to-talk error:", err);
        setIsThinking(false);
      }
    };

    mr.start();
    setIsListening(true);
  }, [memoryContext, messages]);

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
