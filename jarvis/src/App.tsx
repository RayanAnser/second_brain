import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { ConversationArea } from "./components/ConversationArea";
import { Sidebar } from "./components/Sidebar";
import { useStore } from "./store";
import type { Capture, MemoryContext } from "./types";

export default function App() {
  const { setMemoryContext, setCaptures } = useStore();
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    invoke("debug_memory").then((info) => console.log("[jarvis] debug_memory:", info)).catch(console.error);
    invoke<MemoryContext>("read_memory_context").then(setMemoryContext).catch(console.error);
  }, []);

  useEffect(() => {
    const unlisten = listen<string>("claude-capture", (e) => {
      if (toastTimer.current) clearTimeout(toastTimer.current);
      setToast(e.payload);
      toastTimer.current = setTimeout(() => setToast(null), 2000);
      invoke<Capture[]>("read_staging").then(setCaptures).catch(console.error);
    });
    return () => { unlisten.then((fn) => fn()); };
  }, []);

  return (
    <div className="h-screen bg-surface text-[#e0e0f0] flex flex-col">
      {/* Custom drag region titlebar */}
      <div
        data-tauri-drag-region
        className="h-8 bg-surface border-b border-border flex items-center px-4 shrink-0"
      >
        <span className="text-xs text-muted font-mono tracking-[0.3em]">JARVIS</span>
        <div className="ml-auto flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-[#3a7bfd] animate-pulse" />
        </div>
      </div>

      {/* Main layout */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-hidden">
          <ConversationArea />
        </main>
      </div>

      {/* Capture toast */}
      {toast && (
        <div className="fixed bottom-4 right-4 z-50 bg-[#252640] border border-[#4a4b6e] rounded px-3 py-1.5 text-xs text-[#e0e0f0] font-mono pointer-events-none shadow-lg">
          {toast}
        </div>
      )}
    </div>
  );
}
