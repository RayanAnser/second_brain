import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";

type ResizeDirection = "East" | "North" | "NorthEast" | "NorthWest" | "South" | "SouthEast" | "SouthWest" | "West";
import { ConversationArea } from "./components/ConversationArea";
import { ContextWidgets } from "./components/ContextWidgets";
import { OrbVisualizer } from "./components/OrbVisualizer";
import { useClaudeStream } from "./hooks/useClaudeStream";
import { useGeminiLive } from "./hooks/useGeminiLive";
import { useStore } from "./store";
import type { Capture, MemoryContext } from "./types";
import type { OrbState } from "./components/OrbVisualizer";
import type { WidgetsContext } from "./components/ContextWidgets";

const COMPACT_DELAY_MS = 4000;

const INTENT_ICON: Record<string, string> = {
  CAPTURE_IDEE:    "💡",
  CAPTURE_PROJET:  "🚀",
  CAPTURE_CONCEPT: "🧠",
  CAPTURE_PERSO:   "👤",
};

function FloatingCard({
  capture,
  onDelete,
  style,
}: {
  capture: Capture;
  onDelete: () => void;
  style?: CSSProperties;
}) {
  const [hovered, setHovered] = useState(false);
  const icon = INTENT_ICON[capture.intent] ?? "📌";

  return (
    <div
      style={style}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={`flex items-center h-10 rounded-xl overflow-hidden pointer-events-auto
                  bg-black/30 backdrop-blur-md border border-white/10
                  transition-all duration-200 ease-out cursor-default select-none
                  ${hovered ? "w-64" : "w-10"}`}
    >
      <span className="w-10 h-10 flex-shrink-0 flex items-center justify-center text-sm leading-none">
        {icon}
      </span>
      <div
        className={`flex items-center gap-1 pr-2 min-w-0 flex-1 transition-opacity duration-100
                    ${hovered ? "opacity-100 delay-75" : "opacity-0"}`}
      >
        <p className="text-[11px] text-white/80 truncate flex-1">{capture.content}</p>
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
          className="text-white/30 hover:text-white/80 text-[10px] flex-shrink-0 leading-none transition-colors"
        >
          ✕
        </button>
      </div>
    </div>
  );
}

export default function App() {
  const {
    setMemoryContext, setCaptures, captures,
    isListening, isThinking, isSpeaking, audioLevel,
    isCompact, setIsCompact,
    messages,
  } = useStore();

  useClaudeStream();
  const { startListening, stopListening } = useGeminiLive();

  // ── Last assistant response for orb mode display ──────────────────────────
  const lastAssistant = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") return messages[i];
    }
    return null;
  }, [messages]);

  const compactText = useMemo(() => {
    if (!lastAssistant) return null;
    const plain = lastAssistant.content
      .replace(/```[\s\S]*?```/g, "")
      .replace(/\*\*(.+?)\*\*/g, "$1")
      .replace(/\*(.+?)\*/g, "$1")
      .replace(/^#{1,6}\s+/gm, "")
      .replace(/\n+/g, " ")
      .trim();
    return plain.slice(0, 130) || null;
  }, [lastAssistant]);

  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clickTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [isPinned, setIsPinned] = useState(false);
  const [widgetsCtx, setWidgetsCtx] = useState<WidgetsContext | null>(null);

  const orbState: OrbState = isListening ? "listening"
                           : isThinking  ? "thinking"
                           : isSpeaking  ? "speaking"
                           : "idle";

  // ── Window mode helpers ────────────────────────────────────────────────────
  const expandWindow = useCallback(() => {
    invoke("set_window_extended").catch(console.error);
    setIsCompact(false);
  }, [setIsCompact]);

  // Single click → toggle micro. Double click → expand only (no mic).
  const handleOrbClick = useCallback(() => {
    if (clickTimer.current) {
      clearTimeout(clickTimer.current);
      clickTimer.current = null;
      expandWindow();
      setIsPinned(true);
    } else {
      clickTimer.current = setTimeout(() => {
        clickTimer.current = null;
        if (isListening) stopListening();
        else startListening();
      }, 220);
    }
  }, [isListening, startListening, stopListening, expandWindow]);

  // Clear pending click timer if mode changes (compact → extended)
  useEffect(() => {
    if (!isCompact && clickTimer.current) {
      clearTimeout(clickTimer.current);
      clickTimer.current = null;
    }
  }, [isCompact]);

  // ── Boot ───────────────────────────────────────────────────────────────────
  useEffect(() => {
    invoke("debug_memory").then((info) => console.log("[jarvis] debug_memory:", info)).catch(console.error);
    invoke<MemoryContext>("read_memory_context").then(setMemoryContext).catch(console.error);
    invoke<Capture[]>("fetch_staging").then(setCaptures).catch(console.error);
    invoke<WidgetsContext>("read_widgets_context").then(setWidgetsCtx).catch(console.error);
  }, []);

  // Poll captures every 5s
  useEffect(() => {
    const id = setInterval(
      () => invoke<Capture[]>("fetch_staging").then(setCaptures).catch(console.error),
      5000,
    );
    return () => clearInterval(id);
  }, []);

  // Capture toast
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

  // ── Global Ctrl+Space hotkey (emitted from Rust) ───────────────────────────
  useEffect(() => {
    const unlistenStart = listen("hotkey-listen-start", () => {
      if (isCompact) {
        if (isListening) stopListening(); else startListening();
      } else {
        startListening();
      }
    });
    const unlistenStop = listen("hotkey-listen-stop", () => {
      if (!isCompact) stopListening();
    });
    return () => {
      unlistenStart.then((fn) => fn());
      unlistenStop.then((fn) => fn());
    };
  }, [isCompact, isListening, startListening, stopListening]);

  // ── Spacebar binding ───────────────────────────────────────────────────────
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.code === "Space" && !e.repeat && !(e.target as HTMLElement)?.matches("input,textarea")) {
        e.preventDefault();
        if (isCompact) {
          if (isListening) stopListening(); else startListening();
        } else {
          startListening();
        }
      }
    };
    const up = (e: KeyboardEvent) => {
      if (e.code === "Space" && !isCompact) stopListening();
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [isCompact, isListening, startListening, stopListening]);

  // ── Auto-collapse to compact after inactivity ─────────────────────────────
  useEffect(() => {
    if (isCompact || isPinned) return;
    if (isListening || isThinking || isSpeaking) return;
    const timer = setTimeout(() => {
      invoke("set_window_compact").catch(console.error);
      setIsCompact(true);
    }, COMPACT_DELAY_MS);
    return () => clearTimeout(timer);
  }, [isListening, isThinking, isSpeaking, isCompact, isPinned, setIsCompact]);

  // ── Captures ───────────────────────────────────────────────────────────────
  const deleteCapture = (i: number) => {
    if (deleting) return;
    setDeleting(true);
    invoke<Capture[]>("delete_staging", { index: i })
      .then(setCaptures)
      .catch((e) => console.error("[jarvis] delete_staging erreur:", e))
      .finally(() => setDeleting(false));
  };

  const visibleCards = captures.slice(0, 5);

  // ── COMPACT MODE ───────────────────────────────────────────────────────────
  if (isCompact) {
    return (
      <div className="relative h-screen overflow-hidden" style={{ background: "transparent" }}>
        <div className="absolute inset-0 pointer-events-none">
          <OrbVisualizer state={orbState} audioLevel={audioLevel} />
        </div>

        {/* Drag + single-click=toggle micro, double-click=expand */}
        <div
          data-tauri-drag-region
          className="absolute inset-0 cursor-move"
          onClick={handleOrbClick}
        />

        {/* Last response — hidden while listening */}
        {compactText && !isListening && (
          <div className="absolute inset-x-4 bottom-10 pointer-events-none">
            <p
              key={lastAssistant!.id}
              className="text-center text-[11px] text-indigo-300 font-mono leading-relaxed line-clamp-3 select-none"
              style={{
                animation: "orb-text-in 0.6s ease-out forwards",
                textShadow: "0 0 8px rgba(99,102,241,0.8)",
              }}
            >
              {compactText}{lastAssistant!.content.length > 130 ? "…" : ""}
            </p>
          </div>
        )}
      </div>
    );
  }

  // ── EXTENDED MODE ──────────────────────────────────────────────────────────
  return (
    <div className="relative h-screen overflow-hidden bg-[#0a0a0f]">

      {/* ── Full-canvas orb — first in DOM, no z-index; UI elements below paint over it ── */}
      <div className="absolute inset-0 pointer-events-none">
        <OrbVisualizer state={orbState} audioLevel={audioLevel} />
      </div>

      {/* ── Context widgets ── */}
      {widgetsCtx && <ContextWidgets ctx={widgetsCtx} />}

      {/* ── Titlebar ── */}
      <div className="absolute top-0 left-0 right-0 z-20 h-8 bg-black/20 backdrop-blur-sm">
        <div
          data-tauri-drag-region
          className="absolute inset-0 flex items-center px-4"
        >
          <div className="w-2 h-2 rounded-full bg-indigo-400/60 animate-pulse pointer-events-none" />
          <span className="absolute inset-0 flex items-center justify-center text-xs text-white/20 font-mono tracking-[0.3em] pointer-events-none select-none">
            JARVIS
          </span>
        </div>
        <button
          onClick={() => { getCurrentWindow().close(); }}
          className="absolute right-2 top-1/2 -translate-y-1/2 z-10 w-6 h-6 flex items-center justify-center rounded text-white/20 hover:text-white/70 hover:bg-white/10 transition-colors text-sm leading-none"
          aria-label="Fermer"
        >
          ✕
        </button>
      </div>

      {/* ── Floating capture cards — right edge ── */}
      <div
        className="absolute right-3 z-10 flex flex-col items-end gap-0 pointer-events-none"
        style={{ top: "2.75rem", bottom: "7rem" }}
      >
        {visibleCards.map((c, i) => (
          <FloatingCard
            key={`${c.intent}-${c.content.slice(0, 20)}-${i}`}
            capture={c}
            onDelete={() => deleteCapture(i)}
            style={{ marginTop: i > 0 ? "-4px" : undefined }}
          />
        ))}
      </div>

      {/* ── Conversation overlay — bottom center ── */}
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[600px] z-10">
        <ConversationArea startListening={startListening} stopListening={stopListening} />
      </div>

      {/* ── Resize handles ── */}
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
            getCurrentWindow().startResizeDragging(dir);
          }}
        />
      ))}

      {/* ── Pin button (bottom-right) ── */}
      <button
        onClick={() => setIsPinned((p) => !p)}
        title={isPinned ? "Désépingler (auto-collapse actif)" : "Épingler (désactiver auto-collapse)"}
        className={`absolute bottom-3 right-3 z-20 w-7 h-7 flex items-center justify-center rounded-lg transition-colors text-sm leading-none
                    ${isPinned
                      ? "text-indigo-400/80 bg-white/10 hover:bg-white/20"
                      : "text-white/20 hover:text-white/50 hover:bg-white/10"}`}
      >
        {isPinned ? "📌" : "⤢"}
      </button>

      {/* ── Capture toast ── */}
      {toast && (
        <div className="fixed bottom-4 right-4 z-50 bg-black/40 backdrop-blur-md border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white/80 font-mono pointer-events-none">
          {toast}
        </div>
      )}
    </div>
  );
}
