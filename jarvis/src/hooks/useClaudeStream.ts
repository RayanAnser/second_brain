import { useEffect } from "react";
import { listen } from "@tauri-apps/api/event";
import { useStore } from "../store";

export function useClaudeStream() {
  const { appendToLastAssistant, setIsThinking } = useStore();

  useEffect(() => {
    const p1 = listen<string>("claude-token", (e) => {
      appendToLastAssistant(e.payload);
    });

    const p2 = listen<void>("claude-done", () => {
      console.log("[jarvis] claude-done reçu");
      setIsThinking(false);
    });

    const p3 = listen<string>("claude-capture", (e) => {
      console.log("[jarvis] claude-capture reçu:", e.payload);
    });

    return () => {
      p1.then((fn) => fn());
      p2.then((fn) => fn());
      p3.then((fn) => fn());
    };
  }, [appendToLastAssistant, setIsThinking]);
}
