import { useEffect, useState } from "react";
import { control, type State } from "../feed";
import { BLUE } from "../types";
import { agentColor } from "./Panel";

export function TopBar({ s }: { s: State }) {
  const [now, setNow] = useState(new Date());
  const [busy, setBusy] = useState<string | null>(null);
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const act = async (action: string, body: Record<string, unknown> = {}) => {
    setBusy(action);
    try { await control(action, body); } finally { setTimeout(() => setBusy(null), 600); }
  };

  const breached = s.stats.real_records_exposed > 0;
  const lock = s.lockdown.state;
  const status = breached ? "Containment breached" : lock === "on" ? "Lockdown active" : lock === "countdown" ? "Lockdown pending" : "Containment holding";
  const statusColor = breached ? "var(--trap)" : lock !== "off" ? "var(--warn)" : "var(--ok)";

  return (
    <header className="panel flex items-center gap-5 px-4 py-2.5">
      <div className="flex items-center gap-3">
        <svg width="30" height="30" viewBox="0 0 32 32" aria-hidden>
          <path d="M3 16 A13 13 0 0 1 29 16" fill="none" stroke="var(--trap)" strokeWidth="3" />
          <path d="M3 16 A13 13 0 0 0 29 16" fill="none" stroke="var(--real)" strokeWidth="3" />
          <circle cx="16" cy="16" r="3" fill="var(--text)" />
        </svg>
        <div>
          <div className="font-display font-bold tracking-[.2em] text-lg leading-none">FLYTRAP</div>
          <div className="text-[11px] text-text2 tracking-widest uppercase">HackUMass Labs · containment console</div>
        </div>
      </div>

      <div className="flex items-center gap-2 pl-4 border-l border-line">
        <span className="w-2.5 h-2.5 rounded-full animate-pulse" style={{ background: statusColor }} />
        <span className="font-display font-semibold uppercase tracking-widest" style={{ color: statusColor }}>{status}</span>
      </div>

      <div className="flex items-center gap-2 pl-4 border-l border-line" aria-label="Blue swarm status">
        {BLUE.map((a) => {
          const r = s.roster[a];
          const offline = r?.state === "offline";
          return (
            <div key={a} title={`${a}: ${r?.state ?? "watching"}${r?.mode ? ` (${r.mode})` : ""}`} className="flex flex-col items-center">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: offline ? "#3a4450" : agentColor(a), boxShadow: r?.state === "acting" ? `0 0 10px ${agentColor(a)}` : "none" }} />
              <span className="text-[10px] uppercase tracking-wider text-text2 mt-0.5">{a.slice(0, 4)}</span>
            </div>
          );
        })}
      </div>

      <div className="ml-auto flex items-center gap-2">
        {s.replay.active && <span className="px-2 py-1 text-xs rounded bg-warn/20 text-warn font-display tracking-widest">REPLAY · {s.replay.run}</span>}
        {s.mock && <span className="px-2 py-1 text-xs rounded border border-line text-text2">mock feed</span>}
        <span className="text-xs" style={{ color: s.connected ? "var(--ok)" : "var(--trap)" }}>{s.connected ? "● live" : "● offline"}</span>
        <button className="btn btn-trap" disabled={busy !== null} onClick={() => act("release")}>Release the swarm</button>
        <button className="btn" disabled={busy !== null} onClick={() => act("reset")}>Reset Tartarus</button>
        <button className="btn" disabled={busy !== null} onClick={() => act("stop")} title="Kill switch: stop every raider, drone and the crowd">Kill switch</button>
        {lock === "off"
          ? <button className="btn btn-warn" disabled={busy !== null} onClick={() => act("lockdown")}>Lockdown</button>
          : <button className="btn btn-ok" disabled={busy !== null} onClick={() => act("cancel")}>End lockdown</button>}
        <time className="font-display text-xl tabular-nums pl-3 border-l border-line">{now.toLocaleTimeString([], { hour12: false })}</time>
      </div>
    </header>
  );
}
