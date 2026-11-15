import { useState, type MouseEvent } from "react";
import { CardTitle, GlowCard, toSmoothPath } from "@/components/ui/glow-card";

const EVERY_S = 2; // dash-api publishes stats every 2 s
const COLUMNS = 14; // the faint columns behind the plot

const nice = (v: number) => {
  const step = v <= 4 ? 1 : v <= 10 ? 2 : v <= 25 ? 5 : v <= 50 ? 10 : 25;
  return Math.max(step * 4, Math.ceil((v * 1.15) / step) * step);
};
const fmt = (v: number) => (v >= 10 ? v.toFixed(0) : v.toFixed(1));

/** Requests per second over the last two minutes: trapped (bright, glowing) against real. Hover moves the band. */
export function Traffic({ rps, className = "" }: { rps: { real: number; trap: number }[]; className?: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const series = rps.length >= 2 ? rps : null;
  const top = nice(series ? Math.max(...series.map((d) => Math.max(d.real, d.trap))) : 4);
  const at = (i: number, k: "real" | "trap") => ({ x: (i / ((series?.length ?? 2) - 1)) * 100, y: 96 - ((series?.[i]?.[k] ?? 0) / top) * 90 });
  const pts = (k: "real" | "trap") => (series ?? []).map((_, i) => at(i, k));
  const idx = hover ?? (series ? series.length - 1 : 0);
  const cur = series?.[idx] ?? { real: 0, trap: 0 };
  // change against the reading 30 s before the one shown
  const was = series?.[Math.max(0, idx - 15)] ?? cur;
  const delta = (k: "real" | "trap") => {
    const d = cur[k] - was[k];
    return `${d > 0 ? "+" : d < 0 ? "−" : "±"}${fmt(Math.abs(d))}`;
  };

  const onMove = (e: MouseEvent<HTMLDivElement>) => {
    if (!series) return;
    const r = e.currentTarget.getBoundingClientRect();
    setHover(Math.round(Math.min(Math.max((e.clientX - r.left) / r.width, 0), 1) * (series.length - 1)));
  };
  const band = series ? at(idx, "trap").x : 100;
  const legend = (
        <dl className="grid grid-cols-[auto_auto_auto_auto] items-center gap-x-2 gap-y-0.5 rounded-xl border border-line2/60 bg-inner px-2.5 py-1.5 text-[12px] shadow-[0_8px_24px_rgba(0,0,0,.35)]">
          <span className="h-1.5 w-1.5 rounded-full bg-green" />
          <dt className="font-semibold">Trapped</dt>
          <dd className="text-right font-mono tabular text-green">{fmt(cur.trap)}/s</dd>
          <dd className="text-right font-mono text-[11px] tabular text-text2">{delta("trap")}</dd>
          <span className="h-1.5 w-1.5 rounded-full bg-text" />
          <dt className="font-semibold">Real</dt>
          <dd className="text-right font-mono tabular">{fmt(cur.real)}/s</dd>
          <dd className="text-right font-mono text-[11px] tabular text-text2">{delta("real")}</dd>
          <dd className="col-span-4 mt-0.5 text-[10.5px] text-text2">{hover !== null && series ? `${(series.length - 1 - idx) * EVERY_S} s ago · ` : "now · "}change over 30 s</dd>
        </dl>
  );

  return (
    <GlowCard label="Traffic" className={className}>
      <CardTitle right={legend} sub="Requests per second, live. Real visitors stay on Olympus; anything that touched bait is in Tartarus.">Traffic</CardTitle>

      <div className="flex min-h-0 flex-1 pl-8">
        <div className="relative min-h-[110px] flex-1 cursor-crosshair" onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
          {[0, 1, 2, 3, 4].map((k) => (
            <span key={k} aria-hidden className="absolute -left-8 w-6 -translate-y-1/2 text-right font-mono text-[11px] tabular text-text2" style={{ top: `${96 - k * 22.5}%` }}>
              {((top / 4) * k).toFixed(0)}
            </span>
          ))}
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full overflow-visible" role="img"
            aria-label={series ? `Requests per second over the last ${(series.length - 1) * EVERY_S} seconds: trapped ${cur.trap}, real ${cur.real}` : "No traffic readings yet"}>
            <defs>
              <linearGradient id="dolos-col" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgb(228,240,232)" stopOpacity="0.045" />
                <stop offset="100%" stopColor="rgb(228,240,232)" stopOpacity="0" />
              </linearGradient>
              <linearGradient id="dolos-band" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgb(236,236,236)" stopOpacity="0.02" />
                <stop offset="100%" stopColor="rgb(236,236,236)" stopOpacity="0.16" />
              </linearGradient>
            </defs>
            {Array.from({ length: COLUMNS }, (_, i) => (
              <rect key={i} x={(i / COLUMNS) * 100 + 0.9} width={100 / COLUMNS - 1.8} y="0" height="100" rx="1.5" fill="url(#dolos-col)" />
            ))}
            {series && (
              <>
                <rect x={band - 2.6} width="5.2" y="0" height="100" rx="2" fill="url(#dolos-band)" />
                <path d={toSmoothPath(pts("real"))} fill="none" stroke="rgb(228,240,232)" strokeOpacity=".85" strokeWidth="2" vectorEffect="non-scaling-stroke" />
                <path d={toSmoothPath(pts("trap"))} fill="none" stroke="var(--green)" strokeWidth="2.75" strokeLinecap="round" vectorEffect="non-scaling-stroke"
                  style={{ filter: "drop-shadow(0 0 8px rgba(61,255,143,.55))" }} />
              </>
            )}
          </svg>
          {series ? (
            <>
              <span aria-hidden className="pointer-events-none absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-bg bg-text"
                style={{ left: `${at(idx, "real").x}%`, top: `${at(idx, "real").y}%` }} />
              <span aria-hidden className="pointer-events-none absolute h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-[#d7ffe7] bg-green shadow-[0_0_14px_rgba(61,255,143,.9)]"
                style={{ left: `${at(idx, "trap").x}%`, top: `${at(idx, "trap").y}%` }} />
            </>
          ) : (
            <p className="absolute inset-x-0 top-1/2 -translate-y-1/2 text-center text-sm text-text2">The chart fills in as readings arrive, one every {EVERY_S} seconds.</p>
          )}
        </div>
      </div>
    </GlowCard>
  );
}
