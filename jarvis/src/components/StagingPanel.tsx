import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useStore } from "../store";
import type { Capture } from "../types";

const INTENT_LABEL: Record<string, string> = {
  CAPTURE_IDEE:    "💡 Idée",
  CAPTURE_PROJET:  "🚀 Projet",
  CAPTURE_CONCEPT: "🧠 Concept",
  CAPTURE_PERSO:   "👤 Perso",
  MEMORY:          "💾 Mémoire",
};

export function StagingPanel() {
  const { captures, setCaptures } = useStore();
  const [deleting,   setDeleting]   = useState(false);
  const [committing, setCommitting] = useState(false);

  const loadCaptures = () =>
    invoke<Capture[]>("fetch_staging")
      .then(setCaptures)
      .catch((e) => console.error("[jarvis] fetch_staging erreur:", e));

  useEffect(() => {
    loadCaptures();
    const id = setInterval(loadCaptures, 5000);
    return () => clearInterval(id);
  }, []);

  const deleteCapture = (i: number) => {
    if (deleting) return;
    setDeleting(true);
    invoke<Capture[]>("delete_staging", { index: i })
      .then(setCaptures)
      .catch((e) => console.error("[jarvis] delete_staging erreur:", e))
      .finally(() => setDeleting(false));
  };

  const commitMemory = (i: number) => {
    if (committing) return;
    setCommitting(true);
    invoke<Capture[]>("commit_memory_item", { index: i })
      .then(setCaptures)
      .catch((e) => console.error("[jarvis] commit_memory_item erreur:", e))
      .finally(() => setCommitting(false));
  };

  if (captures.length === 0) {
    return (
      <p className="text-xs text-muted text-center py-4">
        Aucune capture en attente.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {captures.map((c, i) => {
        const isMemory = c.intent === "MEMORY";
        return (
          <div
            key={i}
            className={`rounded-md p-2.5 flex items-start gap-2 border ${
              isMemory
                ? "border-amber-500/25 bg-amber-950/20"
                : "border-border"
            }`}
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                <span
                  className={`text-[10px] font-medium ${
                    isMemory ? "text-amber-400" : "text-primary"
                  }`}
                >
                  {INTENT_LABEL[c.intent] ?? c.intent}
                </span>
                {isMemory && c.section && (
                  <span className="text-[9px] text-amber-500/50 font-mono">
                    → {c.section}
                  </span>
                )}
              </div>
              <p className="text-xs text-[#e0e0f0] mt-1 leading-relaxed">
                {c.content}
              </p>
            </div>

            {isMemory ? (
              <div className="flex gap-1 flex-shrink-0 mt-0.5">
                <button
                  onClick={() => commitMemory(i)}
                  disabled={committing}
                  title="Écrire dans la mémoire"
                  className={`text-[10px] leading-none px-1.5 py-0.5 rounded transition-colors ${
                    committing
                      ? "text-muted opacity-30 cursor-not-allowed"
                      : "text-amber-400/80 hover:text-amber-300 hover:bg-amber-900/30"
                  }`}
                >
                  ✓
                </button>
                <button
                  onClick={() => deleteCapture(i)}
                  disabled={deleting}
                  title="Ignorer"
                  className={`text-xs leading-none transition-colors ${
                    deleting
                      ? "text-muted opacity-30 cursor-not-allowed"
                      : "text-muted hover:text-red-400"
                  }`}
                >
                  ✕
                </button>
              </div>
            ) : (
              <button
                onClick={() => deleteCapture(i)}
                disabled={deleting}
                className={`text-xs leading-none flex-shrink-0 mt-0.5 transition-colors ${
                  deleting
                    ? "text-muted opacity-30 cursor-not-allowed"
                    : "text-muted hover:text-red-400"
                }`}
              >
                ✕
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
