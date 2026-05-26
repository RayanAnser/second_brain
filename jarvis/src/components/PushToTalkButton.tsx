import { useStore } from "../store";

interface Props {
  onStart: () => void;
  onStop: () => void;
}

export function PushToTalkButton({ onStart, onStop }: Props) {
  const { isListening } = useStore();

  return (
    <button
      onMouseDown={onStart}
      onMouseUp={onStop}
      onMouseLeave={onStop}
      style={isListening ? { boxShadow: "0 0 20px #6366f1, 0 0 40px #6366f160" } : undefined}
      className={`w-12 h-12 rounded-full flex items-center justify-center transition-all duration-150 focus:outline-none
        ${isListening
          ? "bg-indigo-500/80 scale-110"
          : "bg-black/30 backdrop-blur-md border border-white/10 hover:border-white/30 hover:scale-105"
        }`}
    >
      <svg className="w-5 h-5 text-white/90" fill="currentColor" viewBox="0 0 24 24">
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3zm-1 14.93V18H9v2h6v-2h-2v-2.07A7 7 0 0 0 19 11h-2a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.93z" />
      </svg>
    </button>
  );
}
