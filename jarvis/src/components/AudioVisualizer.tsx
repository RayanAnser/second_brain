import { useRef, useEffect } from "react";
import { useStore } from "../store";

export function AudioVisualizer() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { isListening, isSpeaking, isThinking, audioLevel } = useStore();

  const isActive = isListening || isSpeaking || isThinking;
  const color = isListening ? "#3a7bfd" : isSpeaking ? "#00d4aa" : isThinking ? "#a855f7" : "#2a2a3e";

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    const W = canvas.width;
    const H = canvas.height;
    const cx = W / 2;
    const cy = H / 2;
    const BARS = 40;
    const BASE_R = 44;

    let phase = 0;
    let animId: number;

    const draw = () => {
      ctx.clearRect(0, 0, W, H);

      // Outer orbit dots
      for (let i = 0; i < BARS; i++) {
        const angle = (i / BARS) * Math.PI * 2 - Math.PI / 2;
        const noise = isActive
          ? audioLevel * 28 * Math.abs(Math.sin(phase * 2.5 + i * 0.4)) +
            (isSpeaking ? Math.sin(phase * 4 + i) * 6 : 0)
          : 0;
        const r = BASE_R + noise;

        ctx.beginPath();
        ctx.arc(cx + Math.cos(angle) * r, cy + Math.sin(angle) * r, 2, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.globalAlpha = isActive ? 0.5 + audioLevel * 0.5 : 0.15;
        ctx.fill();
      }

      // Inner ring
      ctx.beginPath();
      ctx.arc(cx, cy, BASE_R - 10, 0, Math.PI * 2);
      ctx.strokeStyle = color;
      ctx.globalAlpha = isActive ? 0.25 + audioLevel * 0.3 : 0.08;
      ctx.lineWidth = 1;
      ctx.stroke();

      // Center dot
      ctx.beginPath();
      ctx.arc(cx, cy, isActive ? 5 + audioLevel * 4 : 3, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.globalAlpha = isActive ? 0.9 : 0.2;
      ctx.fill();

      ctx.globalAlpha = 1;
      phase += 0.04;
      animId = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(animId);
  }, [isListening, isSpeaking, isThinking, audioLevel, color, isActive]);

  return <canvas ref={canvasRef} width={160} height={160} className="mx-auto" />;
}
