import { useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { ConversationArea } from "./components/ConversationArea";
import { Sidebar } from "./components/Sidebar";
import { useStore } from "./store";
import type { MemoryContext } from "./types";

export default function App() {
  const { setMemoryContext } = useStore();

  useEffect(() => {
    invoke("debug_memory").then((info) => console.log("[jarvis] debug_memory:", info)).catch(console.error);
    invoke<MemoryContext>("read_memory_context").then(setMemoryContext).catch(console.error);
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
    </div>
  );
}
