import { useState, type MouseEvent } from "react";
import { CardTitle, GlowCard, toSmoothPath, useAnimatedNumber } from "@/components/ui/glow-card";
import type { StatsData } from "@/types";

const EVERY_S = 2; // dash-api publishes stats every 2 s

/** Requests per second: trapped (bright, solid) against real (sage, dashed). */
export function Traffic({ rps, stats, className = "" }: {
  rps: { real: number; trap: number }[]; stats: StatsData; className?: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const series = rps.length >= 2 ? rps : null;
  const latest = rps[rps.length - 1] ?? { real: 0, trap: 0 };
  const trapNow = useAnimatedNumber(latest.trap, 600);
  const realNow = useAnimatedNumber(latest.real, 600);

  const max = series ? Math.max(1, ...series.map((d) => Math.max(d.real, d.trap))) : 1;
  const pts = (k: "real" | "trap") =>
    (series ?? []).map((d, i, a) => ({ x: (i / (a.length - 1)) * 100, y: 95 - (d[k] / max) * 85 }));
  const trapPts = pts("trap");
  const trapLine = toSmoothPath(trapPts);
  const realLine = toSmoothPath(pts("real"));
  const shown = hover ?? (series ? series.length - 1 : 0);

  const onMove = (e: MouseEvent<HTMLDivElement>) => {
    if (!series) return;
    const r = e.currentTarget.getBoundingClientRect();
    const f = Math.min(Math.max((e.clientX - r.left) / r.width, 0), 1);
    setHover(Math.round(f * (series.length - 1)));
  };

  return (
    <GlowCard label="Traffic" className={className}>
      <CardTitle right={<span className="flex items-center gap-1.5 text-xs text-green"><span className="dolos-pulse h-1.5 w-1.5 rounded-full bg-green" />live</span>}>
        Requests per second
      </CardTitle>

      <div className="flex flex-wrap items-end gap-x-8 gap-y-2">
        <div>
          <span className="font-display text-[clamp(3rem,4.6vw,4.5rem)] font-[300] leading-[.82] tabular text-green">{trapNow.toFixed(1)}</span>
          <span className="caps ml-2 text-[10px] text-text2">trapped</span>
        </div>
        <div>
          <span className="font-display text-[clamp(2rem,3vw,3rem)] font-[300] leading-[.82] tabular text-real">{realNow.toFixed(1)}</span>
          <span className="caps ml-2 text-[10px] text-text2">real</span>
        </div>
        <p className="ml-auto text-xs text-text2">
          gateway p50 <b className="font-mono font-medium text-text">{stats.p50_gw_ms?.toFixed(2) ?? "—"}</b> · p95{" "}
          <b className="font-mono font-medium text-text">{stats.p95_gw_ms?.toFixed(2) ?? "—"}</b> ms
        </p>
      </div>

      {series ? (
        <>
          <div className="relative mt-3 min-h-[44px] flex-1 cursor-crosshair" onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full overflow-visible" role="img"
              aria-label={`Requests per second over the last ${(series.length - 1) * EVERY_S} seconds: trapped ${latest.trap}, real ${latest.real} now`}>
              <defs>
                <linearGradient id="dolos-trap-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="rgb(61,255,143)" stopOpacity="0.28" />
                  <stop offset="100%" stopColor="rgb(61,255,143)" stopOpacity="0" />
                </linearGradient>
              </defs>
              {[25, 50, 75].map((y) => (
                <line key={y} x1="0" x2="100" y1={y} y2={y} stroke="rgba(228,240,232,.06)" strokeDasharray="3 4" vectorEffect="non-scaling-stroke" />
              ))}
              <path d={`${trapLine} L 100 100 L 0 100 Z`} fill="url(#dolos-trap-fill)" />
              <path d={realLine} fill="none" stroke="var(--real)" strokeWidth="1.5" strokeDasharray="5 4" vectorEffect="non-scaling-stroke" />
              <path d={trapLine} fill="none" stroke="var(--green)" strokeWidth="2.5" strokeLinecap="round" vectorEffect="non-scaling-stroke"
                style={{ filter: "drop-shadow(0 0 6px rgba(61,255,143,.6))" }} />
              {hover !== null && (
                <line x1={trapPts[hover].x} x2={trapPts[hover].x} y1="0" y2="100" stroke="rgba(61,255,143,.4)" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />
              )}
            </svg>
            <span aria-hidden className="pointer-events-none absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-[#d7ffe7] bg-green shadow-[0_0_12px_rgba(61,255,143,.9)]"
              style={{ left: `${trapPts[shown].x}%`, top: `${trapPts[shown].y}%` }} />
            {hover !== null && (
              <div aria-hidden className="pointer-events-none absolute -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-lg border border-line2 bg-panel/95 px-2.5 py-1.5 text-xs shadow-xl"
                style={{ left: `clamp(56px, ${trapPts[hover].x}%, calc(100% - 56px))`, top: `calc(${trapPts[hover].y}% - 14px)` }}>
                <div className="text-text2">{(series.length - 1 - hover) * EVERY_S}s ago</div>
                <div className="font-mono"><span className="text-green">{series[hover].trap}</span> trapped · <span className="text-real">{series[hover].real}</span> real</div>
              </div>
            )}
          </div>
          <div className="mt-1.5 flex shrink-0 justify-between text-[11px] leading-none text-text2">
            <span>{(series.length - 1) * EVERY_S}s ago</span>
            <span className="flex items-center gap-4">
              <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 bg-green" />trapped</span>
              <span className="flex items-center gap-1.5"><span className="h-0 w-4 border-t border-dashed border-real" />real</span>
            </span>
            <span>now</span>
          </div>
        </>
      ) : (
        <p className="mt-6 text-sm text-text2">The chart fills in as readings arrive, one every {EVERY_S} seconds.</p>
      )}
    </GlowCard>
  );
}
