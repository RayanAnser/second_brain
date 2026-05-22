import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import type { DocEntry } from "../types";

const SUBDIR_ICON: Record<string, string> = {
  projets:  "📁",
  concepts: "🧠",
  perso:    "👤",
};

export function MemorySearch() {
  const [keyword, setKeyword]         = useState("");
  const [docs, setDocs]               = useState<DocEntry[]>([]);
  const [selected, setSelected]       = useState<{ name: string; content: string } | null>(null);

  useEffect(() => {
    const kw = keyword.trim() || undefined;
    invoke<DocEntry[]>("list_docs", { keyword: kw })
      .then(setDocs)
      .catch(console.error);
  }, [keyword]);

  const openDoc = async (doc: DocEntry) => {
    try {
      const content = await invoke<string>("read_doc", { relKey: doc.key });
      setSelected({ name: doc.name, content });
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <input
        type="text"
        placeholder="Rechercher..."
        value={keyword}
        onChange={(e) => setKeyword(e.target.value)}
        className="w-full bg-surface border border-border rounded px-3 py-1.5 text-xs text-[#e0e0f0] placeholder-muted outline-none focus:border-primary"
      />

      <div className="space-y-0.5 max-h-52 overflow-y-auto">
        {docs.map((doc) => (
          <button
            key={doc.key}
            onClick={() => openDoc(doc)}
            className={`w-full text-left flex items-center gap-2 px-2 py-1.5 rounded text-xs transition-colors
              ${selected?.name === doc.name
                ? "bg-[#1a2a4a] text-[#e0e0f0]"
                : "hover:bg-panel text-[#e0e0f0]"
              }`}
          >
            <span className="text-base leading-none">{SUBDIR_ICON[doc.subdir] ?? "📄"}</span>
            <span className="flex-1 truncate">{doc.name}</span>
            <span className="text-muted shrink-0">{doc.size_kb.toFixed(1)}K</span>
          </button>
        ))}
        {docs.length === 0 && (
          <p className="text-xs text-muted text-center py-3">Aucun fichier trouvé.</p>
        )}
      </div>

      {selected && (
        <div className="border border-border rounded-md overflow-hidden">
          <div className="flex items-center justify-between px-2.5 py-1.5 bg-panel border-b border-border">
            <span className="text-[10px] font-medium text-primary truncate">{selected.name}</span>
            <button
              onClick={() => setSelected(null)}
              className="text-muted hover:text-[#e0e0f0] text-xs ml-2 shrink-0"
            >
              ✕
            </button>
          </div>
          <pre className="text-xs text-[#c0c0d8] p-2.5 whitespace-pre-wrap font-mono overflow-y-auto max-h-52 leading-relaxed">
            {selected.content}
          </pre>
        </div>
      )}
    </div>
  );
}
