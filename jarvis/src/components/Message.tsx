import { useState } from "react";
import type { Message as MessageType } from "../types";

export function Message({ role, content }: MessageType) {
  const [copied, setCopied] = useState(false);
  const isUser = role === "user";

  const copy = () => {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  return (
    <div className={`group flex ${isUser ? "justify-end" : "justify-start"} mb-1.5`}>
      <div className={`relative max-w-[88%] text-sm leading-relaxed
        ${isUser ? "text-right text-white/90" : "text-left text-white/75"}`}
      >
        <p className="whitespace-pre-wrap">{content}</p>

        <button
          onClick={copy}
          aria-label="Copier"
          className={`absolute -bottom-4 opacity-0 group-hover:opacity-60 hover:!opacity-100 transition-opacity
            text-[10px] text-white/60 leading-none select-none pointer-events-auto
            ${isUser ? "right-0" : "left-0"}`}
        >
          {copied ? "✓" : "⎘"}
        </button>
      </div>
    </div>
  );
}
