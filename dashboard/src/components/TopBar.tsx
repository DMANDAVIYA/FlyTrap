import { Lock, LockOpen, PanelRightClose, PanelRightOpen, Power, Radar, RotateCcw } from "lucide-react";
import { useState } from "react";
import { control, type State } from "../feed";
import { DolosMark, Wordmark } from "./Logo";
import { Scramble } from "./Scramble";

export function TopBar({ s, drawerOpen, onToggleDrawer }: { s: State; drawerOpen: boolean; onToggleDrawer: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);

  const act = async (action: string, body: Record<string, unknown> = {}) => {
    setBusy(action);
    try { await control(action, body); } finally { setTimeout(() => setBusy(null), 600); }
  };

  const breached = s.stats.real_records_exposed > 0;
  const lock = s.lockdown.state;
  const status = breached ? "Containment breached" : lock === "on" ? "Lockdown active" : lock === "countdown" ? "Lockdown pending" : "Containment holding";
  const statusColor = breached ? "var(--trap)" : lock !== "off" ? "var(--warn)" : "var(--ok)";
  const DrawerIcon = drawerOpen ? PanelRightClose : PanelRightOpen;

  return (
    <header className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-line px-4 py-2.5">
      <a href="#/" className="flex items-center gap-2.5" aria-label="Dolos home">
        <DolosMark />
        <Wordmark className="text-[15px]" />
        <span className="text-text2 text-sm">console</span>
      </a>

      <div className="flex items-center gap-2 pl-5 border-l border-line">
        <span className={`h-2.5 w-2.5 rounded-full ${breached || lock !== "off" ? "animate-pulse" : ""}`} style={{ background: statusColor }} />
        <span className="font-mono text-[13px] font-bold uppercase tracking-[0.14em]" style={{ color: statusColor }}>
          <Scramble text={status} />
        </span>
      </div>

      <div className="flex items-center gap-3 text-xs">
        <span className="flex items-center gap-1.5" style={{ color: s.connected ? "var(--ok)" : "var(--trap)" }}>
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: "currentColor" }} />
          {s.connected ? "live" : "offline"}
        </span>
        {s.replay.active && <span className="rounded-[3px] bg-warn/15 px-2 py-1 font-mono font-bold tracking-[0.14em] text-warn">REPLAY · {s.replay.run}</span>}
        {s.mode && s.mode !== "live" && <span className="rounded-[3px] border border-line px-2 py-1 text-text2">{s.mode}</span>}
      </div>

      <div className="ml-auto flex flex-wrap items-center gap-2">
        <button className="btn btn-trap" disabled={busy !== null} onClick={() => act("release")}>
          <Radar size={14} aria-hidden /> Release the swarm
        </button>
        <button className="btn" disabled={busy !== null} onClick={() => act("reset")}>
          <RotateCcw size={14} aria-hidden /> Reset Tartarus
        </button>
        <button className="btn" disabled={busy !== null} onClick={() => act("stop")} title="Stop every raider, drone and the crowd">
          <Power size={14} aria-hidden /> Kill switch
        </button>
        {lock === "off" ? (
          <button className="btn btn-warn" disabled={busy !== null} onClick={() => act("lockdown")}>
            <Lock size={14} aria-hidden /> Lockdown
          </button>
        ) : (
          <button className="btn btn-ok" disabled={busy !== null} onClick={() => act("cancel_lockdown")}>
            <LockOpen size={14} aria-hidden /> End lockdown
          </button>
        )}
        <button className="btn ml-1" aria-expanded={drawerOpen} aria-controls="details" onClick={onToggleDrawer}>
          <DrawerIcon size={14} aria-hidden /> Details
        </button>
      </div>
    </header>
  );
}
