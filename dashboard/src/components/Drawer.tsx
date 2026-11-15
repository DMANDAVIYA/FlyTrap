import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { X } from "lucide-react";
import { useEffect } from "react";
import type { State } from "../feed";
import { Loot } from "./Loot";
import { Replay } from "./Replay";
import { Report } from "./Report";
import { Roster } from "./Roster";
import { Stream } from "./Streams";

export const TABS = ["Agents", "Trackers", "Report", "Roster", "Replay"] as const;
export type Tab = (typeof TABS)[number];

/** Everything that is not needed at a glance. A side panel, not a modal: the map stays live beside it. */
export function Drawer({ s, open, tab, onTab, onClose, picked, onPick }: {
  s: State; open: boolean; tab: Tab; onTab: (t: Tab) => void; onClose: () => void;
  picked: string | null; onPick: (sid: string) => void;
}) {
  const reduce = useReducedMotion();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const badge: Partial<Record<Tab, number>> = { Trackers: s.campaigns.length + s.canaries.length, Report: Object.keys(s.reports).length };

  return (
    <AnimatePresence>
      {open && (
        <motion.aside
          id="details"
          aria-label="Details"
          initial={reduce ? false : { x: "100%" }}
          animate={{ x: 0 }}
          exit={reduce ? { opacity: 0 } : { x: "100%" }}
          transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
          className="absolute inset-y-0 right-0 z-40 flex w-[min(560px,100%)] flex-col border-l border-line2 bg-bg shadow-[-24px_0_48px_rgba(0,0,0,.55)]"
        >
          <div className="flex items-center border-b border-line">
          <div role="tablist" aria-label="Details" className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto px-2">
            {TABS.map((t) => (
              <button
                key={t}
                role="tab"
                aria-selected={t === tab}
                onClick={() => onTab(t)}
                className={`relative shrink-0 px-3 py-3 text-[12px] font-semibold uppercase tracking-[0.12em] transition-colors ${
                  t === tab ? "text-text" : "text-text2 hover:text-text"
                }`}
              >
                {t}
                {!!badge[t] && <span className="ml-1.5 font-mono text-[11px] text-matrix">{badge[t]}</span>}
                {t === tab && <span className="absolute inset-x-3 bottom-0 h-0.5 bg-matrix" />}
              </button>
            ))}
          </div>
          <button aria-label="Close details" onClick={onClose} className="mx-1 shrink-0 rounded-[3px] p-2 text-text2 hover:text-text">
            <X size={16} aria-hidden />
          </button>
          </div>

          <div role="tabpanel" className="flex min-h-0 flex-1 flex-col">
            {tab === "Agents" && (
              <>
                <Stream title="Red swarm · raiders" items={s.red} color="var(--trap)" empty="Raiders are idle." className="flex-1 border-b border-line" />
                <Stream title="Blue swarm · defenders" items={s.blue} color="var(--real)" empty="Defenders are watching." className="flex-1" />
              </>
            )}
            {tab === "Trackers" && <Loot s={s} className="flex-1" />}
            {tab === "Report" && <Report s={s} picked={picked} onPick={onPick} className="flex-1" />}
            {tab === "Roster" && <Roster s={s} />}
            {tab === "Replay" && (
              <div className="flex flex-col gap-3 p-4">
                <Replay s={s} />
                <p className="text-sm text-text2">Plays a recorded run through the whole console. Live mode reconnects to the running lab.</p>
              </div>
            )}
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
