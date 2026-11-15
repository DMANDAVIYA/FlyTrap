import { AnimatePresence, motion } from "framer-motion";
import { lazy, Suspense, useEffect, useState } from "react";
import type { State } from "../feed";
import { short } from "./Panel";

const TrapMap = lazy(() => import("./three/TrapMap"));

export function LiveMap({ s }: { s: State }) {
  const [flip, setFlip] = useState(s.lastFlip);
  useEffect(() => {
    if (!s.lastFlip) return;
    setFlip(s.lastFlip);
    const id = setTimeout(() => setFlip(null), 2600);
    return () => clearTimeout(id);
  }, [s.lastFlip]);

  return (
    <section aria-label="Live map" className="relative min-h-0 bg-bg overflow-hidden">
      <Suspense fallback={<p className="p-6 text-sm text-text2">Loading the map…</p>}>
        <div className="absolute inset-0">
          <TrapMap />
        </div>
      </Suspense>

      <div className="pointer-events-none absolute left-4 bottom-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text2">
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-real" />real visitor → Olympus</span>
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-trap" />trapped → Tartarus</span>
        <span className="font-mono tabular">{s.flips} flips</span>
      </div>
      <p className="pointer-events-none absolute right-4 bottom-4 hidden sm:block text-[11px] text-text2/70">Drag to orbit · scroll to zoom</p>

      <AnimatePresence>
        {flip && (
          <motion.div
            key={flip.at}
            role="status"
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            style={{ x: "-50%" }}
            className="pointer-events-none absolute left-1/2 top-4 rounded-[3px] border border-trap bg-[#14050a]/90 px-4 py-2.5 shadow-[0_12px_32px_rgba(0,0,0,.55)]"
          >
            <div className="flex items-baseline gap-3 whitespace-nowrap">
              <span className="font-mono text-[11px] font-bold uppercase tracking-[0.24em] text-trap">Trapped</span>
              <span className="expanded font-semibold">{flip.raider ?? short(flip.session)}</span>
              <span className="text-text2 text-sm">→ {flip.pod} · {flip.tripwire}</span>
              <span className="font-mono text-sm tabular text-text2">{Number(flip.gw_ms).toFixed(2)} ms</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
