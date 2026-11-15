import { AnimatePresence, motion } from "framer-motion";
import { Lock, LockOpen, PanelRightClose, PanelRightOpen, Power, Radar, RotateCcw } from "lucide-react";
import { useState } from "react";
import { control, type State } from "../feed";
import { DolosMark, Wordmark } from "./Logo";

export function TopBar({ s, drawerOpen, onToggleDrawer }: { s: State; drawerOpen: boolean; onToggleDrawer: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);

  const act = async (action: string, body: Record<string, unknown> = {}) => {
    setBusy(action);
    try { await control(action, body); } finally { setTimeout(() => setBusy(null), 600); }
  };

  const breached = s.stats.real_records_exposed > 0;
  const lock = s.lockdown.state;
  const status = breached ? "Containment breached" : lock === "on" ? "Lockdown active" : lock === "countdown" ? "Lockdown pending" : "Containment holding";
  const statusColor = breached ? "var(--breach)" : lock !== "off" ? "var(--warn)" : "var(--ok)";
  const DrawerIcon = drawerOpen ? PanelRightClose : PanelRightOpen;

  return (
    <header className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-line px-4 py-3 sm:px-6">
      <a href="#/" className="flex items-center gap-3" aria-label="Dolos home">
        <DolosMark />
        <Wordmark className="text-[13px]" />
        <span className="caps text-[10px] text-text2">console</span>
      </a>

      <div className="flex items-center gap-2.5 sm:border-l sm:border-line sm:pl-6" role="status">
        <span className={`h-2 w-2 rounded-full ${breached || lock !== "off" ? "animate-pulse" : ""}`} style={{ background: statusColor }} />
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={status}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.2 }}
            className="caps text-[11px] font-bold"
            style={{ color: statusColor }}
          >
            {status}
          </motion.span>
        </AnimatePresence>
      </div>

      <div className="flex items-center gap-3 text-xs">
        <span className="flex items-center gap-1.5" style={{ color: s.connected ? "var(--ok)" : "var(--text-2)" }}>
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: "currentColor" }} />
          {s.connected ? "live" : "offline"}
        </span>
        {s.replay.active && <span className="caps rounded-full bg-warn/15 px-2.5 py-1 text-[10px] font-bold text-warn">Replay · {s.replay.run}</span>}
        {s.mode && s.mode !== "live" && <span className="rounded-full border border-line px-2.5 py-1 text-text2">{s.mode}</span>}
      </div>

      <div className="ml-auto flex flex-wrap items-center gap-2">
        <button className="btn btn-trap" aria-label="Release the swarm" disabled={busy !== null} onClick={() => act("release")}>
          <Radar size={14} aria-hidden /> <span className="sm:hidden">Release</span><span className="hidden sm:inline">Release the swarm</span>
        </button>
        <button className="btn" aria-label="Reset Tartarus" disabled={busy !== null} onClick={() => act("reset")}>
          <RotateCcw size={14} aria-hidden /> <span className="sm:hidden">Reset</span><span className="hidden sm:inline">Reset Tartarus</span>
        </button>
        <button className="btn" aria-label="Kill switch" disabled={busy !== null} onClick={() => act("stop")} title="Stop every raider, drone and the crowd">
          <Power size={14} aria-hidden /> <span className="sm:hidden">Kill</span><span className="hidden sm:inline">Kill switch</span>
        </button>
        {lock === "off" ? (
          <button className="btn btn-warn" aria-label="Lockdown" disabled={busy !== null} onClick={() => act("lockdown")}>
            <Lock size={14} aria-hidden /> <span className="sm:hidden">Lock</span><span className="hidden sm:inline">Lockdown</span>
          </button>
        ) : (
          <button className="btn btn-ok" aria-label="End lockdown" disabled={busy !== null} onClick={() => act("cancel_lockdown")}>
            <LockOpen size={14} aria-hidden /> <span className="sm:hidden">Unlock</span><span className="hidden sm:inline">End lockdown</span>
          </button>
        )}
        <button className="btn" aria-label="Details" aria-expanded={drawerOpen} aria-controls="details" onClick={onToggleDrawer}>
          <DrawerIcon size={14} aria-hidden /> <span className="sm:hidden">Details</span><span className="hidden sm:inline">Details</span>
        </button>
      </div>
    </header>
  );
}
