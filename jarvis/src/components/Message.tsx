import { useState } from "react";
import type { Message as MessageType } from "../types";

export function Message({ role, content, timestamp }: MessageType) {
  const [copied, setCopied] = useState(false);

  const time = new Date(timestamp).toLocaleTimeString("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
  });

  const copy = () => {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  const isUser = role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-2`}>
      <div
        className={`group relative max-w-[80%] rounded-lg px-3.5 py-2.5 text-sm leading-relaxed
          ${isUser
            ? "bg-[#1a2a4a] text-[#e0e0f0] ml-10"
            : "bg-panel border border-border text-[#e0e0f0] mr-10"
          }`}
      >
        <p className="whitespace-pre-wrap">{content}</p>
        <span className="text-[10px] text-muted mt-1 block text-right">{time}</span>

        {/* Copy button — visible on group hover */}
        <button
          onClick={copy}
          aria-label="Copier"
          className={`absolute -bottom-5 opacity-30 group-hover:opacity-100 transition-opacity
            text-[10px] text-[#a0a0c0] hover:text-[#e0e0f0] leading-none select-none
            ${isUser ? "right-1" : "left-1"}`}
        >
          {copied ? "✓" : "⎘"}
        </button>
      </div>
    </div>
  );
}
