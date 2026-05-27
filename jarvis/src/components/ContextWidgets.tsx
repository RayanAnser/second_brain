import { useEffect, useState } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────
export interface AgendaItem  { time: string; label: string; }
export interface ProjectItem { name: string; status: string; }
export interface WidgetsContext {
  agenda:   AgendaItem[];
  projects: ProjectItem[];
  threads:  string[];
  taches:   string[];
}

// ── Shared glass card ─────────────────────────────────────────────────────────
function GlassCard({ children, className = "", onHoverChange }: {
  children: React.ReactNode;
  className?: string;
  onHoverChange?: (h: boolean) => void;
}) {
  const [hovered, setHovered] = useState(false);
  const enter = () => { setHovered(true);  onHoverChange?.(true);  };
  const leave = () => { setHovered(false); onHoverChange?.(false); };

  return (
    <div
      onMouseEnter={enter}
      onMouseLeave={leave}
      className={`bg-black/30 backdrop-blur-md border rounded-xl overflow-hidden
                  transition-all duration-300 ease-out cursor-default select-none ${className}`}
      style={{
        borderColor: hovered ? "rgba(255,255,255,0.18)" : "rgba(255,255,255,0.08)",
        boxShadow:   hovered ? "0 0 22px rgba(99,102,241,0.12), inset 0 0 0 0.5px rgba(255,255,255,0.06)"
                             : "none",
        transform:   hovered ? "scale(1.025)" : "scale(1)",
      }}
    >
      {children}
    </div>
  );
}

function Header({ icon, title }: { icon: string; title: string }) {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 border-b border-white/[0.06]">
      <span className="text-xs leading-none opacity-70">{icon}</span>
      <span className="text-[9px] font-mono text-white/25 tracking-[0.18em] uppercase">{title}</span>
    </div>
  );
}

// ── Status color ──────────────────────────────────────────────────────────────
function statusColor(s: string): string {
  const sl = s.toLowerCase();
  if (sl.includes("v0.") || sl.includes("sprint") || sl.includes("terminé")) return "text-emerald-400/75";
  if (sl.includes("veille"))   return "text-yellow-400/60";
  if (sl.includes("idée"))     return "text-white/25";
  if (sl.includes("test"))     return "text-blue-400/65";
  return "text-white/40";
}

// ── Widgets ───────────────────────────────────────────────────────────────────
export function ContextWidgets({ ctx }: { ctx: WidgetsContext }) {
  const [show, setShow] = useState(false);
  const [threadsExpanded, setThreadsExpanded] = useState(false);
  const [tachesExpanded, setTachesExpanded]   = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setShow(true), 80);
    return () => clearTimeout(t);
  }, []);

  const PREVIEW     = 3;
  const taches      = ctx.taches  ?? [];
  const threads     = ctx.threads ?? [];
  const extraTaches  = taches.length  - PREVIEW;
  const extraThreads = threads.length - PREVIEW;

  return (
    <div
      className={`transition-opacity duration-500 ${show ? "opacity-100" : "opacity-0"}`}
      style={{ pointerEvents: "none" }}
    >

      {/* ── Agenda — top-left ──────────────────────────────────────────────── */}
      {ctx.agenda.length > 0 && (
        <div className="absolute top-10 left-3 z-10 w-52" style={{ pointerEvents: "auto" }}>
          <GlassCard>
            <Header icon="⏱" title="Agenda" />
            <div className="px-3 py-2.5 space-y-1.5">
              {ctx.agenda.map((item, i) => (
                <div key={i} className="flex gap-2.5 items-baseline min-w-0">
                  <span className="text-[11px] font-mono text-indigo-400/80 tabular-nums flex-shrink-0 leading-tight">
                    {item.time}
                  </span>
                  <span className="text-[11px] text-white/65 truncate leading-tight">
                    {item.label}
                  </span>
                </div>
              ))}
            </div>
          </GlassCard>
        </div>
      )}

      {/* ── Projets — center-left ─────────────────────────────────────────── */}
      {ctx.projects.length > 0 && (
        <div className="absolute top-1/2 -translate-y-1/2 left-3 z-10 w-52" style={{ pointerEvents: "auto" }}>
          <GlassCard>
            <Header icon="◈" title="Projets" />
            <div className="px-3 py-2.5 space-y-2.5">
              {ctx.projects.map((p, i) => (
                <div key={i} className="min-w-0">
                  <p className="text-[11px] text-white/72 truncate leading-tight">{p.name}</p>
                  <p className={`text-[10px] font-mono leading-tight truncate mt-0.5 ${statusColor(p.status)}`}>
                    {p.status}
                  </p>
                </div>
              ))}
            </div>
          </GlassCard>
        </div>
      )}

      {/* ── Tâches + Fils ouverts — bottom-left, stacked, grow upward ─────── */}
      <div
        className="absolute bottom-32 left-3 z-10 w-52 flex flex-col gap-2"
        style={{ pointerEvents: "none" }}
      >
        {/* Tâches */}
        {taches.length > 0 && (
          <div style={{ pointerEvents: "auto" }}>
            <GlassCard onHoverChange={setTachesExpanded}>
              <Header icon="📋" title="Tâches" />
              <div
                className="px-3 pt-2 overflow-hidden transition-all duration-300 ease-out"
                style={{
                  maxHeight: tachesExpanded
                    ? `${taches.length * 20 + 20}px`
                    : `${PREVIEW * 20 + 12}px`,
                }}
              >
                {taches.map((t, i) => (
                  <p
                    key={i}
                    className="text-[11px] leading-snug truncate pb-1 transition-opacity duration-200"
                    style={{
                      color:   `rgba(255,255,255,${Math.max(0.3, 0.70 - i * 0.08)})`,
                      opacity: i < PREVIEW || tachesExpanded ? 1 : 0,
                    }}
                  >
                    {t}
                  </p>
                ))}
              </div>
              {extraTaches > 0 && (
                <p
                  className="px-3 pb-2 text-[9px] font-mono text-white/20 transition-opacity duration-200"
                  style={{ opacity: tachesExpanded ? 0 : 1 }}
                >
                  +{extraTaches} autres
                </p>
              )}
            </GlassCard>
          </div>
        )}

        {/* Fils ouverts */}
        {threads.length > 0 && (
          <div style={{ pointerEvents: "auto" }}>
            <GlassCard onHoverChange={setThreadsExpanded}>
              <Header icon="◎" title="Fils ouverts" />
              <div
                className="px-3 pt-2 overflow-hidden transition-all duration-300 ease-out"
                style={{
                  maxHeight: threadsExpanded
                    ? `${threads.length * 20 + 20}px`
                    : `${PREVIEW * 20 + 12}px`,
                }}
              >
                {threads.map((t, i) => (
                  <p
                    key={i}
                    className="text-[11px] leading-snug truncate pb-1 transition-opacity duration-200"
                    style={{
                      color:   `rgba(255,255,255,${Math.max(0.3, 0.70 - i * 0.08)})`,
                      opacity: i < PREVIEW || threadsExpanded ? 1 : 0,
                    }}
                  >
                    {t}
                  </p>
                ))}
              </div>
              {extraThreads > 0 && (
                <p
                  className="px-3 pb-2 text-[9px] font-mono text-white/20 transition-opacity duration-200"
                  style={{ opacity: threadsExpanded ? 0 : 1 }}
                >
                  +{extraThreads} autres
                </p>
              )}
            </GlassCard>
          </div>
        )}
      </div>
    </div>
  );
}
