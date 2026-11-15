import { motion, useReducedMotion } from "framer-motion";
import type { StatsData } from "../types";

function Vital({ label, value, unit, color, note, big = false }: {
  label: string; value: string; unit?: string; color: string; note: string; big?: boolean;
}) {
  const reduce = useReducedMotion();
  return (
    <div className="px-4 py-3.5">
      <h2 className="panel-title">{label}</h2>
      <motion.div
        key={value}
        initial={reduce ? false : { opacity: 0.35, y: -4 }}
        animate={{ opacity: 1, y: 0 }}
        className={`mt-1.5 font-mono font-bold tabular leading-none ${big ? "text-[56px]" : "text-[32px]"}`}
        style={{ color }}
      >
        {value}
        {unit && <span className="ml-1 text-base font-medium text-text2">{unit}</span>}
      </motion.div>
      <p className="mt-1.5 text-xs text-text2">{note}</p>
    </div>
  );
}

/** The three numbers the demo is about. */
export function Counters({ stats }: { stats: StatsData }) {
  const exposed = stats.real_records_exposed;
  return (
    <section aria-label="Vitals" className="border-b border-line">
      <Vital big label="Real records exposed" value={String(exposed)} color={exposed ? "var(--breach)" : "var(--ok)"}
        note={exposed ? "Real customer records were served on Olympus" : "Not one real customer record has left Olympus"} />
      <div className="grid grid-cols-2 border-t border-line divide-x divide-line">
        <Vital label="Trapped" value={String(stats.trapped)} color="var(--trap)" note={`${stats.active_sessions ?? 0} active sessions`} />
        <Vital label="Flip time" value={stats.avg_flip_ms != null ? stats.avg_flip_ms.toFixed(2) : "—"} unit="ms" color="var(--real)" note="average decision" />
      </div>
    </section>
  );
}
