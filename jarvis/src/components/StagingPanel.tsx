import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useStore } from "../store";
import type { Capture } from "../types";

const INTENT_LABEL: Record<string, string> = {
  CAPTURE_IDEE:    "💡 Idée",
  CAPTURE_PROJET:  "🚀 Projet",
  CAPTURE_CONCEPT: "🧠 Concept",
  CAPTURE_PERSO:   "👤 Perso",
};

export function StagingPanel() {
  const { captures, setCaptures } = useStore();
  const [deleting, setDeleting] = useState(false);

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

  if (captures.length === 0) {
    return (
      <p className="text-xs text-muted text-center py-4">
        Aucune capture en attente.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {captures.map((c, i) => (
        <div key={i} className="border border-border rounded-md p-2.5 flex items-start gap-2">
          <div className="flex-1 min-w-0">
            <span className="text-[10px] font-medium text-primary">
              {INTENT_LABEL[c.intent] ?? c.intent}
            </span>
            <p className="text-xs text-[#e0e0f0] mt-1 leading-relaxed">{c.content}</p>
          </div>
          <button
            onClick={() => deleteCapture(i)}
            disabled={deleting}
            className={`text-xs leading-none flex-shrink-0 mt-0.5 ${
              deleting ? "text-muted opacity-30 cursor-not-allowed" : "text-muted hover:text-red-400"
            }`}
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
