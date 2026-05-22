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
      className={`w-12 h-12 rounded-full flex items-center justify-center transition-all duration-150 focus:outline-none
        ${isListening
          ? "bg-primary shadow-[0_0_20px_rgba(58,123,253,0.5)] scale-110"
          : "bg-panel border border-border hover:border-muted hover:scale-105"
        }`}
    >
      <svg className="w-5 h-5 text-[#e0e0f0]" fill="currentColor" viewBox="0 0 24 24">
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3zm-1 14.93V18H9v2h6v-2h-2v-2.07A7 7 0 0 0 19 11h-2a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.93z" />
      </svg>
    </button>
  );
}
