import { useStore } from "../store";
import { Message } from "./Message";
import { PushToTalkButton } from "./PushToTalkButton";

const BASE_OPACITIES = [0.3, 0.6, 1.0];

interface Props {
  startListening: () => void;
  stopListening: () => void;
}

export function ConversationArea({ startListening, stopListening }: Props) {
  const { messages, isListening, isSpeaking, isThinking } = useStore();

  const lastThree = messages.slice(-3);
  const opacities = BASE_OPACITIES.slice(BASE_OPACITIES.length - lastThree.length);

  const statusText = isListening ? "Écoute en cours..."
                   : isThinking  ? "Réflexion..."
                   : isSpeaking  ? "Lecture..."
                   : "Espace ou clic pour parler";

  return (
    <div className="flex flex-col items-center px-4 pb-4 pointer-events-none">

      {/* Message stream — last 3, fading upward */}
      {lastThree.length > 0 && (
        <div
          className="w-full mb-3"
          style={{ maskImage: "linear-gradient(to bottom, transparent 0%, black 40%)" }}
        >
          {lastThree.map((msg, i) => (
            <div
              key={msg.id}
              style={{ opacity: opacities[i] }}
              className="transition-opacity duration-500"
            >
              <Message {...msg} />
            </div>
          ))}
        </div>
      )}

      {/* Controls */}
      <div className="flex flex-col items-center gap-2 pointer-events-auto">
        <PushToTalkButton onStart={startListening} onStop={stopListening} />
        <p className="text-[11px] text-white/30 select-none">{statusText}</p>
      </div>
    </div>
  );
}
