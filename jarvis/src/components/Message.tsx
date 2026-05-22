import type { Message as MessageType } from "../types";

export function Message({ role, content, timestamp }: MessageType) {
  const time = new Date(timestamp).toLocaleTimeString("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className={`flex ${role === "user" ? "justify-end" : "justify-start"} mb-2`}>
      <div
        className={`max-w-[80%] rounded-lg px-3.5 py-2.5 text-sm leading-relaxed
          ${role === "user"
            ? "bg-[#1a2a4a] text-[#e0e0f0] ml-10"
            : "bg-panel border border-border text-[#e0e0f0] mr-10"
          }`}
      >
        <p className="whitespace-pre-wrap">{content}</p>
        <span className="text-[10px] text-muted mt-1 block text-right">{time}</span>
      </div>
    </div>
  );
}
