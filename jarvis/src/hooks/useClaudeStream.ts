import { useEffect } from "react";
import { listen } from "@tauri-apps/api/event";
import { useStore } from "../store";
import { useTTS } from "./useTTS";

export function useClaudeStream() {
  const { appendToLastAssistant, setIsThinking } = useStore();
  const { speak } = useTTS();

  useEffect(() => {
    let accumulated = "";

    const p1 = listen<string>("claude-token", (e) => {
      appendToLastAssistant(e.payload);
      accumulated += e.payload;
    });

    const p2 = listen<void>("claude-done", () => {
      setIsThinking(false);
      if (accumulated.trim()) {
        speak(accumulated);
        accumulated = "";
      }
    });

    return () => {
      p1.then((fn) => fn());
      p2.then((fn) => fn());
    };
  }, []);
}
