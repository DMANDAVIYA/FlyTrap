import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { control } from "../feed";
import type { LockdownData } from "../types";

export function LockdownOverlay({ lock }: { lock: LockdownData }) {
  const [left, setLeft] = useState(lock.seconds ?? 10);
  useEffect(() => {
    if (lock.state !== "countdown") return;
    setLeft(lock.seconds ?? 10);
    const id = setInterval(() => setLeft((x) => Math.max(0, x - 1)), 1000);
    return () => clearInterval(id);
  }, [lock.state, lock.seconds]);

  return (
    <AnimatePresence>
      {lock.state !== "off" && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          className="fixed inset-x-0 top-0 z-50 pointer-events-none">
          <div className="stripes h-3" />
          <div className="mx-auto mt-2 w-fit pointer-events-auto rounded border border-warn bg-[#1a1408]/95 px-5 py-3 flex items-center gap-4 shadow-2xl">
            <span className="font-display font-bold text-2xl tracking-[.2em] text-warn">
              {lock.state === "countdown" ? `LOCKDOWN IN ${left}s` : "LOCKDOWN"}
            </span>
            <span className="text-sm text-text2 max-w-md">{lock.reason || "Every unknown visitor goes to Tartarus."}</span>
            <button className="btn btn-ok" onClick={() => control("cancel")}>
              {lock.state === "countdown" ? "Cancel" : "End lockdown"}
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
