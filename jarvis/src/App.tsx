import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { getCurrentWindow, type ResizeDirection } from "@tauri-apps/api/window";
import { ConversationArea } from "./components/ConversationArea";
import { OrbVisualizer } from "./components/OrbVisualizer";
import { Sidebar } from "./components/Sidebar";
import { useStore } from "./store";
import type { Capture, MemoryContext } from "./types";
import type { OrbState } from "./components/OrbVisualizer";

export default function App() {
  const { setMemoryContext, setCaptures, isListening, isThinking, isSpeaking, audioLevel } = useStore();
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const orbState: OrbState = isListening ? "listening"
                           : isThinking  ? "thinking"
                           : isSpeaking  ? "speaking"
                           : "idle";

  useEffect(() => {
    invoke("debug_memory").then((info) => console.log("[jarvis] debug_memory:", info)).catch(console.error);
    invoke<MemoryContext>("read_memory_context").then(setMemoryContext).catch(console.error);
  }, []);

  useEffect(() => {
    const unlisten = listen<string>("claude-capture", (e) => {
      if (toastTimer.current) clearTimeout(toastTimer.current);
      setToast(e.payload);
      toastTimer.current = setTimeout(() => setToast(null), 2000);
      const delay = e.payload.includes("supprimé") || e.payload.includes("suppressions") ? 2000
                  : e.payload.includes("noté")     || e.payload.includes("tâche")        ? 800
                  : 0;
      setTimeout(
        () => invoke<Capture[]>("fetch_staging").then(setCaptures).catch(console.error),
        delay,
      );
    });
    return () => { unlisten.then((fn) => fn()); };
  }, []);

  return (
    <div className="h-screen bg-surface text-[#e0e0f0] flex flex-col">
      {/* Titlebar — wrapper positions close button absolutely outside drag-region */}
      <div className="h-8 shrink-0 relative border-b border-border bg-surface/80 backdrop-blur">
        {/* Drag region — full titlebar surface, no interactive children inside */}
        <div
          data-tauri-drag-region
          className="absolute inset-0 flex items-center px-4"
        >
          <div className="w-2 h-2 rounded-full bg-[#3a7bfd] animate-pulse pointer-events-none" />
          <span className="absolute inset-0 flex items-center justify-center text-xs text-muted font-mono tracking-[0.3em] pointer-events-none select-none">
            JARVIS
          </span>
        </div>

        {/* Close button — sibling of drag-region, not a child */}
        <button
          onClick={() => { getCurrentWindow().close(); }}
          className="absolute right-2 top-1/2 -translate-y-1/2 z-10 w-6 h-6 flex items-center justify-center rounded text-muted hover:text-[#e0e0f0] hover:bg-[#3a2040] transition-colors text-sm leading-none"
          aria-label="Fermer"
        >
          ✕
        </button>
      </div>

      {/* Main layout */}
      <div className="flex flex-1 overflow-hidden min-h-0">
        <Sidebar />
        <main className="flex-1 flex flex-col overflow-hidden min-h-0">
          {/* Orb — 45 vh */}
          <div className="shrink-0" style={{ height: "45vh" }}>
            <OrbVisualizer state={orbState} audioLevel={audioLevel} />
          </div>

          {/* Conversation — scrollable remainder */}
          <div className="flex-1 overflow-hidden min-h-0">
            <ConversationArea />
          </div>
        </main>
      </div>

      {/* Resize handles — workaround for decorations:false on Linux */}
      {(
        [
          { dir: "NorthWest" as ResizeDirection, cls: "top-0 left-0 w-2 h-2 cursor-nw-resize"       },
          { dir: "North"     as ResizeDirection, cls: "top-0 left-2 right-2 h-1 cursor-n-resize"    },
          { dir: "NorthEast" as ResizeDirection, cls: "top-0 right-0 w-2 h-2 cursor-ne-resize"      },
          { dir: "West"      as ResizeDirection, cls: "top-2 bottom-2 left-0 w-1 cursor-w-resize"   },
          { dir: "East"      as ResizeDirection, cls: "top-2 bottom-2 right-0 w-1 cursor-e-resize"  },
          { dir: "SouthWest" as ResizeDirection, cls: "bottom-0 left-0 w-2 h-2 cursor-sw-resize"    },
          { dir: "South"     as ResizeDirection, cls: "bottom-0 left-2 right-2 h-1 cursor-s-resize" },
          { dir: "SouthEast" as ResizeDirection, cls: "bottom-0 right-0 w-2 h-2 cursor-se-resize"   },
        ] satisfies Array<{ dir: ResizeDirection; cls: string }>
      ).map(({ dir, cls }) => (
        <div
          key={dir}
          className={`fixed z-[9] ${cls}`}
          onMouseDown={(e) => {
            e.preventDefault();
            console.log("resize triggered", dir);
            getCurrentWindow().startResizeDragging(dir);
          }}
        />
      ))}

      {/* Capture toast */}
      {toast && (
        <div className="fixed bottom-4 right-4 z-50 bg-[#252640] border border-[#4a4b6e] rounded px-3 py-1.5 text-xs text-[#e0e0f0] font-mono pointer-events-none shadow-lg">
          {toast}
        </div>
      )}
    </div>
  );
}
