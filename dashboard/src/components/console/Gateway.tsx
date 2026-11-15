import { CardTitle, GlowCard } from "@/components/ui/glow-card";
import type { Hist } from "@/feed";
import { clock } from "../Panel";

const SHOW = 30; // one minute of 2 s readings

/** Charon's decision time: p50 and p95 per reading, with the request count this run. */
export function Gateway({ hist, requests, className = "" }: { hist: Hist[]; requests?: number; className?: string }) {
  const rows = hist.filter((h) => h.p50 != null || h.p95 != null).slice(-SHOW);
  const top = Math.max(0.5, ...rows.map((h) => h.p95 ?? h.p50 ?? 0)) * 1.2;
  const line = (k: "p50" | "p95") =>
    rows.map((h, i) => `${i ? "L" : "M"} ${(i / Math.max(1, rows.length - 1)) * 100} ${96 - ((h[k] ?? 0) / top) * 90}`).join(" ");
  const ticks = rows.length >= 2 ? [...new Set([0, Math.floor((rows.length - 1) / 2), rows.length - 1])] : [];
  const last = rows[rows.length - 1];
  return (
    <GlowCard label="Gateway" className={className}>
      <CardTitle
        sub={last ? <>p50 <span className="font-mono text-green">{last.p50?.toFixed(2) ?? "—"}</span> · p95 <span className="font-mono text-text">{last.p95?.toFixed(2) ?? "—"}</span> ms</> : "Charon's decision time per request"}
        right={<div className="text-right"><p className="text-[12px] text-text2">Requests</p><p className="text-[22px] font-semibold leading-tight tabular">{(requests ?? 0).toLocaleString()}</p></div>}
      >
        Gateway
      </CardTitle>
      {rows.length >= 2 ? (
        <>
          <div className="relative min-h-[36px] flex-1">
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full overflow-visible" role="img"
              aria-label={`Gateway decision time over the last ${(rows.length - 1) * 2} seconds: p50 ${last.p50} ms, p95 ${last.p95} ms`}>
              {[0, 25, 50, 75, 100].map((y) => <line key={`h${y}`} x1="0" x2="100" y1={y} y2={y} stroke="rgba(228,240,232,.07)" vectorEffect="non-scaling-stroke" />)}
              {[0, 20, 40, 60, 80, 100].map((x) => <line key={`v${x}`} y1="0" y2="100" x1={x} x2={x} stroke="rgba(228,240,232,.05)" vectorEffect="non-scaling-stroke" />)}
              <path d={line("p95")} fill="none" stroke="var(--real)" strokeWidth="1.4" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
              <path d={line("p50")} fill="none" stroke="var(--green)" strokeWidth="1.8" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
            </svg>
          </div>
          <div className="mt-2 flex justify-between font-mono text-[11px] tabular text-text2">
            {ticks.map((i) => <span key={i}>{clock(rows[i].t)}</span>)}
          </div>
        </>
      ) : (
        <p className="text-[12.5px] leading-snug text-text2">The line fills in while this page stays open, one reading every 2 seconds.</p>
      )}
    </GlowCard>
  );
}
