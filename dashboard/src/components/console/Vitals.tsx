import { CardTitle, GlowCard, useAnimatedNumber } from "@/components/ui/glow-card";
import type { StatsData } from "@/types";

function Reading({ label, short, value, unit, color, note, big = false }: {
  label: string; short: string; value: string; unit?: string; color: string; note: string; big?: boolean;
}) {
  return (
    <div className="flex min-w-0 flex-col">
      <CardTitle><span className="sm:hidden">{short}</span><span className="hidden sm:inline">{label}</span></CardTitle>
      <div className={`font-display font-[300] leading-[.82] tabular ${big ? "text-[clamp(3.5rem,8vw,7.5rem)]" : "text-[clamp(2.5rem,5vw,5rem)]"}`} style={{ color }}>
        {value}
        {unit && <span className="ml-1 font-sans text-sm font-medium text-text2">{unit}</span>}
      </div>
      <p className="mt-auto hidden pt-3 text-xs leading-snug text-text2 sm:block">{note}</p>
    </div>
  );
}

/** The three numbers the demo is about. */
export function Vitals({ stats, className = "" }: { stats: StatsData; className?: string }) {
  const exposed = stats.real_records_exposed;
  const trapped = useAnimatedNumber(stats.trapped);
  const flip = stats.avg_flip_ms;
  return (
    <GlowCard label="Vitals" className={className} glow={exposed ? "var(--breach-rgb)" : undefined}>
      <div className="grid h-full grid-cols-[1.2fr_1fr_1fr] gap-4 sm:gap-6">
        <Reading big label="Real records exposed" short="Exposed" value={String(exposed)} color={exposed ? "var(--breach)" : "var(--green)"}
          note={exposed ? "Real customer records were served on Olympus" : "Not one real customer record has left Olympus"} />
        <Reading label="Trapped" short="Trapped" value={String(Math.round(trapped))} color="var(--green)" note={`${stats.active_sessions ?? 0} active sessions`} />
        <Reading label="Flip time" short="Flip" value={flip != null ? flip.toFixed(2) : "—"} unit="ms" color="var(--real)" note="average gateway decision" />
      </div>
    </GlowCard>
  );
}
