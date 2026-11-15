import { Crosshair, Database, KeyRound, ShieldCheck, Users, Zap, type LucideIcon } from "lucide-react";
import { Chip, GlowCard } from "@/components/ui/glow-card";
import type { Hist, State } from "@/feed";

type Key = "trapped" | "active" | "fake" | "keys";

/** Change of one counter over the last minute of live readings (or as much of it as the page has seen). */
function change(hist: Hist[], key: Key) {
  const last = hist[hist.length - 1];
  if (!last || hist.length < 2) return null;
  const from = hist.find((h) => h.t >= last.t - 60_000) ?? hist[0];
  if (from === last) return null;
  return { d: last[key] - from[key], span: (last.t - from.t) / 1000 };
}

const signed = (d: number) => (d > 0 ? `+${d}` : d < 0 ? `−${Math.abs(d)}` : "±0");

function Tile({ icon: Icon, label, value, foot, chip, lead = false }: {
  icon: LucideIcon; label: string; value: string; foot: string; chip: { text: string; tone: "good" | "flat" | "bad" }; lead?: boolean;
}) {
  return (
    <GlowCard label={label} className="min-h-[132px]">
      <div className="flex flex-col items-start gap-3 sm:flex-row sm:gap-3.5">
        <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-[13px] border min-[1440px]:h-12 min-[1440px]:w-12 ${lead ? "border-green bg-green text-[#03140a] shadow-[0_0_24px_rgba(61,255,143,.35)]" : "border-line2/70 bg-inner text-text"}`}>
          <Icon size={21} strokeWidth={1.8} aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="line-clamp-2 text-[12.5px] leading-snug text-text2">{label}</p>
          <p className="mt-0.5 whitespace-nowrap text-[22px] font-semibold leading-tight tracking-[-0.01em] tabular min-[1440px]:text-[26px]">{value}</p>
        </div>
      </div>
      <div className="mt-auto flex items-center justify-between gap-2 border-t border-dashed border-line2 pt-2.5">
        <span className="truncate text-[12.5px] text-text2">{foot}</span>
        <Chip tone={chip.tone}>{chip.text}</Chip>
      </div>
    </GlowCard>
  );
}

/** Six live readings. Changes are measured over the readings this page has received, so the window is named honestly. */
export function Kpis({ s, className = "" }: { s: State; className?: string }) {
  const st = s.stats;
  const exposed = st.real_records_exposed;
  const win = (c: ReturnType<typeof change>) => (!c ? "Waiting for readings" : c.span >= 55 ? "Last minute" : `Last ${Math.round(c.span)} s`);
  const up = (key: Key, goodWhenUp = true) => {
    const c = change(s.hist, key);
    return {
      foot: win(c),
      chip: { text: c ? signed(c.d) : "—", tone: c && c.d > 0 && goodWhenUp ? ("good" as const) : ("flat" as const) },
    };
  };
  const ms = (v: number | null | undefined) => (v == null ? "—" : `${v.toFixed(2)} ms`);

  return (
    <div className={`grid min-h-0 grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-rows-2 ${className}`}>
      <Tile lead icon={ShieldCheck} label="Real records exposed" value={String(exposed)} foot="Customer data"
        chip={exposed ? { text: "Breached", tone: "bad" } : { text: "Holding", tone: "good" }} />
      <Tile icon={Crosshair} label="Trapped" value={String(st.trapped)} {...up("trapped")} />
      <Tile icon={Zap} label="Flip time" value={ms(st.avg_flip_ms)} foot="Gateway p95" chip={{ text: ms(st.p95_gw_ms), tone: "flat" }} />
      <Tile icon={Users} label="Active sessions" value={String(st.active_sessions ?? 0)} {...up("active", false)} />
      <Tile icon={Database} label="Fake records taken" value={st.fake_records_taken.toLocaleString()} {...up("fake")} />
      <Tile icon={KeyRound} label="Marked keys used" value={String(st.canaries_fired)} {...up("keys")} />
    </div>
  );
}
