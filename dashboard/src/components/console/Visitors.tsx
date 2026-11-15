import { CardTitle, GlowCard, useAnimatedNumber } from "@/components/ui/glow-card";
import type { StatsData } from "@/types";

const KINDS = [
  { key: "ai_agent", label: "AI agents" },
  { key: "scanner", label: "Scanners" },
  { key: "human", label: "Humans" },
  { key: "unknown", label: "Not yet labelled" },
];

/** Who is visiting, as Argus labels them, around the total in a lit orb. */
export function Visitors({ stats, className = "" }: { stats: StatsData; className?: string }) {
  const by = stats.sessions_by_label ?? {};
  const total = Object.values(by).reduce((a, b) => a + b, 0);
  const shown = useAnimatedNumber(total);
  return (
    <GlowCard label="Visitors" className={className}>
      <div className="flex min-h-0 flex-1 gap-4">
        <dl className="flex shrink-0 flex-col justify-between gap-3 py-1">
          {KINDS.map((k) => (
            <div key={k.key}>
              <dt className="text-[13px] text-text2">{k.label}</dt>
              <dd className={`text-[26px] font-semibold leading-tight tabular ${k.key === "ai_agent" && by[k.key] ? "text-green" : ""}`}>{by[k.key] ?? 0}</dd>
            </div>
          ))}
        </dl>
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="text-right"><CardTitle>Visitors</CardTitle></div>
          <div className="flex min-h-0 flex-1 items-center justify-center">
            <div className="orb dolos-float grid aspect-square w-[min(100%,15rem)] place-items-center">
              <span className="relative text-[clamp(2rem,3.2vw,2.75rem)] font-light tabular text-text">{Math.round(shown).toLocaleString()}</span>
            </div>
          </div>
          <p className="mt-2 text-center text-[12px] text-text2">{total ? "visitors labelled by Argus" : "Counts appear once visitors arrive"}</p>
        </div>
      </div>
    </GlowCard>
  );
}
