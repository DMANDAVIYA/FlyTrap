import type { CSSProperties } from "react";
import { CardTitle, GlowCard } from "@/components/ui/glow-card";
import type { StatsData } from "@/types";

const KINDS = [
  { key: "ai_agent", label: "AI agents", color: "var(--green)" },
  { key: "scanner", label: "Scanners", color: "var(--real)" },
  { key: "human", label: "Humans", color: "var(--text-2)" },
];
const R = 20;
const C = 2 * Math.PI * R;

/** Who is visiting, as Argus labels them. */
export function Visitors({ stats, className = "" }: { stats: StatsData; className?: string }) {
  const by = stats.sessions_by_label ?? {};
  const total = Object.values(by).reduce((a, b) => a + b, 0);
  return (
    <GlowCard label="Visitor types" className={className}>
      <CardTitle right={<span className="text-xs text-text2">{total} labelled</span>}>Visitors</CardTitle>
      {total ? (
        <ul className="flex flex-1 items-center justify-between gap-2">
          {KINDS.map((k) => {
            const n = by[k.key] ?? 0;
            const share = n / total;
            return (
              <li key={k.key} className="flex flex-col items-center gap-2">
                <div className="relative h-16 w-16">
                  <svg viewBox="0 0 50 50" className="h-full w-full -rotate-90" aria-hidden>
                    <circle cx="25" cy="25" r={R} fill="none" stroke="rgba(228,240,232,.08)" strokeWidth="4" />
                    <circle cx="25" cy="25" r={R} fill="none" stroke={k.color} strokeWidth="4" strokeLinecap="round" strokeDasharray={C}
                      className="dolos-ring" style={{ "--from": `${C}`, "--to": `${C * (1 - share)}`, strokeDashoffset: C * (1 - share) } as CSSProperties} />
                  </svg>
                  <span className="absolute inset-0 flex items-center justify-center font-display text-2xl font-[400] tabular">{n}</span>
                </div>
                <span className="text-[11px] text-text2">{k.label}</span>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-sm leading-relaxed text-text2">Argus labels each visitor as human, scanner or AI agent. Counts appear here once visitors arrive.</p>
      )}
    </GlowCard>
  );
}
