import { invoke } from "@tauri-apps/api/core";
import { useStore } from "../store";

export function useTTS() {
  const { setIsSpeaking } = useStore();

  const speak = async (text: string) => {
    if (!text.trim()) return;
    setIsSpeaking(true);
    try {
      const bytes: number[] = await invoke("synthesize_speech", { text });
      const audioCtx = new AudioContext();
      const buffer = await audioCtx.decodeAudioData(new Uint8Array(bytes).buffer);
      const source = audioCtx.createBufferSource();
      source.buffer = buffer;
      source.connect(audioCtx.destination);
      source.onended = () => {
        setIsSpeaking(false);
        audioCtx.close();
      };
      source.start();
    } catch (err) {
      console.error("TTS error:", err);
      setIsSpeaking(false);
    }
  };

  const cancel = () => {
    // AudioBufferSourceNode has no global cancel; speaking state is reset via onended
    setIsSpeaking(false);
  };

  return { speak, cancel };
}
