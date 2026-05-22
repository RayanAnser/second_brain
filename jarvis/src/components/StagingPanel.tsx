import { useEffect } from "react";
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

  useEffect(() => {
    invoke<Capture[]>("read_staging").then(setCaptures).catch(console.error);
  }, []);

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
        <div key={i} className="border border-border rounded-md p-2.5">
          <span className="text-[10px] font-medium text-primary">
            {INTENT_LABEL[c.intent] ?? c.intent}
          </span>
          <p className="text-xs text-[#e0e0f0] mt-1 leading-relaxed">{c.content}</p>
        </div>
      ))}
    </div>
  );
}
