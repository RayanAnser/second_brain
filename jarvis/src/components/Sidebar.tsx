import { useState } from "react";
import { StagingPanel } from "./StagingPanel";
import { MemorySearch } from "./MemorySearch";
import { useStore } from "../store";

type Tab = "staging" | "memory";

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const [tab, setTab] = useState<Tab>("staging");
  const { captures } = useStore();

  if (collapsed) {
    return (
      <div className="w-9 border-r border-border flex flex-col items-center py-3 gap-3 shrink-0">
        <button
          onClick={() => setCollapsed(false)}
          className="text-muted hover:text-[#e0e0f0] text-xs"
          title="Ouvrir le panneau"
        >
          ▶
        </button>
      </div>
    );
  }

  return (
    <div className="w-64 border-r border-border flex flex-col shrink-0">
      {/* Tab bar */}
      <div className="flex items-stretch border-b border-border shrink-0">
        <TabButton active={tab === "staging"} onClick={() => setTab("staging")}>
          📋
          {captures.length > 0 && (
            <span className="ml-1 bg-primary text-white text-[9px] rounded-full px-1.5 py-px leading-none">
              {captures.length}
            </span>
          )}
        </TabButton>
        <TabButton active={tab === "memory"} onClick={() => setTab("memory")}>
          📁
        </TabButton>
        <button
          onClick={() => setCollapsed(true)}
          className="ml-auto px-2.5 text-muted hover:text-[#e0e0f0] text-[10px]"
        >
          ◀
        </button>
      </div>

      <div className="text-[10px] text-muted px-3 py-1.5 border-b border-border shrink-0">
        {tab === "staging" ? "Captures en attente" : "Fichiers mémoire"}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3">
        {tab === "staging" ? <StagingPanel /> : <MemorySearch />}
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center px-3 py-2 text-sm transition-colors
        ${active
          ? "text-primary border-b-2 border-primary"
          : "text-muted hover:text-[#e0e0f0] border-b-2 border-transparent"
        }`}
    >
      {children}
    </button>
  );
}
