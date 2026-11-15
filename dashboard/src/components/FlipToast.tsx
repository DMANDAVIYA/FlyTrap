import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import type { State } from "../feed";
import { short } from "./Panel";

/** "Trapped X → pod Y": shown for each live flip so the operator never misses one. */
export function FlipToast({ s }: { s: State }) {
  const [flip, setFlip] = useState(s.lastFlip);
  useEffect(() => {
    if (!s.lastFlip) return;
    setFlip(s.lastFlip);
    const id = setTimeout(() => setFlip(null), 2800);
    return () => clearTimeout(id);
  }, [s.lastFlip]);

  return (
    <div className="pointer-events-none fixed inset-x-0 top-16 z-30 flex justify-center px-4" role="status" aria-live="polite">
      <AnimatePresence>
        {flip && (
          <motion.div
            key={flip.at}
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="flex max-w-full items-baseline gap-3 overflow-hidden whitespace-nowrap rounded-full border border-trap/60 bg-[#04140b]/95 px-5 py-2 shadow-[0_12px_32px_rgba(0,0,0,.55)]"
          >
            <span className="caps text-[10.5px] font-bold text-trap">Trapped</span>
            <span className="font-semibold">{flip.raider ?? short(flip.session)}</span>
            <span className="truncate text-sm text-text2">→ {flip.pod} · {flip.tripwire}</span>
            <span className="font-mono text-sm tabular text-text2">{Number(flip.gw_ms).toFixed(2)} ms</span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
