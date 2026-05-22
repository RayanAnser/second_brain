import { useEffect, useRef } from "react";
import { useStore } from "../store";
import { Message } from "./Message";
import { AudioVisualizer } from "./AudioVisualizer";
import { PushToTalkButton } from "./PushToTalkButton";
import { useClaudeStream } from "../hooks/useClaudeStream";
import { usePushToTalk } from "../hooks/usePushToTalk";

export function ConversationArea() {
  useClaudeStream();
  const { startListening, stopListening } = usePushToTalk();
  const { messages, isListening, isSpeaking, isThinking } = useStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const statusText = isListening
    ? "Écoute en cours..."
    : isThinking
    ? "Réflexion..."
    : isSpeaking
    ? "Lecture..."
    : "Maintenez Espace ou cliquez pour parler";

  return (
    <div className="flex flex-col h-full">
      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center text-muted">
            <div className="text-4xl mb-4 opacity-20">◈</div>
            <p className="text-sm">Aucune conversation active</p>
            <p className="text-xs mt-1">Maintenez Espace ou cliquez sur le micro pour parler</p>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <Message key={msg.id} {...msg} />
            ))}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Controls */}
      <div className="border-t border-border px-4 py-4 flex flex-col items-center gap-3 shrink-0">
        <AudioVisualizer />
        <PushToTalkButton onStart={startListening} onStop={stopListening} />
        <p className="text-[11px] text-muted">{statusText}</p>
      </div>
    </div>
  );
}
