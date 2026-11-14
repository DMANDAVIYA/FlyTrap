import { motion, useReducedMotion } from "framer-motion";
import type { StatsData } from "../types";

function Spark({ data }: { data: { real: number; trap: number }[] }) {
  if (data.length < 2) return null;
  const max = Math.max(1, ...data.map((d) => Math.max(d.real, d.trap)));
  const pts = (k: "real" | "trap") => data.map((d, i) => `${(i / (data.length - 1)) * 100},${30 - (d[k] / max) * 28}`).join(" ");
  return (
    <svg viewBox="0 0 100 30" className="w-full h-6" preserveAspectRatio="none" aria-hidden>
      <polyline points={pts("real")} fill="none" stroke="var(--real)" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
      <polyline points={pts("trap")} fill="none" stroke="var(--trap)" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function Counter({ label, value, color, sub, big = false }: { label: string; value: string; color: string; sub?: string; big?: boolean }) {
  const reduce = useReducedMotion();
  return (
    <div className={`panel px-4 py-2 flex flex-col justify-between ${big ? "col-span-4" : "col-span-2"}`}>
      <div className="panel-title">{label}</div>
      <motion.div key={value} initial={reduce ? false : { opacity: 0.4, y: -4 }} animate={{ opacity: 1, y: 0 }}
        className="font-display font-bold tabular-nums leading-none" style={{ color, fontSize: big ? 72 : 52 }}>
        {value}
      </motion.div>
      {sub && <div className="text-xs text-text2 mt-1">{sub}</div>}
    </div>
  );
}

export function Counters({ stats, rps }: { stats: StatsData; rps: { real: number; trap: number }[] }) {
  const exposed = stats.real_records_exposed;
  return (
    <div className="grid grid-cols-12 gap-3">
      <Counter big label="Real records exposed" value={String(exposed)} color={exposed ? "var(--trap)" : "var(--ok)"}
        sub={`Other customers' records served on Olympus (measured from the ledger) · own records: ${stats.real_own_records ?? 0}`} />
      <Counter label="Fake records taken" value={stats.fake_records_taken.toLocaleString()} color="var(--trap)" sub="served inside Tartarus" />
      <Counter label="Trapped" value={String(stats.trapped)} color="var(--trap)" sub={`${stats.active_sessions ?? 0} active sessions`} />
      <Counter label="Trackers fired" value={String(stats.canaries_fired)} color="var(--warn)" sub="stolen keys used" />
      <div className="panel px-4 py-2 col-span-2 flex flex-col justify-between">
        <div className="panel-title">Flip decision</div>
        <div className="font-display font-bold tabular-nums leading-none text-[40px]" style={{ color: "var(--real)" }}>
          {stats.avg_flip_ms != null ? `${stats.avg_flip_ms.toFixed(2)}` : "—"}<span className="text-lg text-text2"> ms</span>
        </div>
        <div className="text-xs text-text2">
          gateway p50 {stats.p50_gw_ms != null ? stats.p50_gw_ms.toFixed(2) : "—"} · p95 {stats.p95_gw_ms != null ? stats.p95_gw_ms.toFixed(2) : "—"} ms
          {" · "}<span style={{ color: "var(--real)" }}>{(stats.rps_real ?? 0).toFixed(1)}</span>/<span style={{ color: "var(--trap)" }}>{(stats.rps_trap ?? 0).toFixed(1)}</span> rps
        </div>
        <Spark data={rps} />
      </div>
    </div>
  );
}
