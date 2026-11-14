import type { State } from "../feed";
import type { SessionData } from "../types";
import { Panel, agentColor, short, sideColor } from "./Panel";

const STAGES = ["recon", "bait", "access", "discovery", "collection", "exfil", "done"];
const LABEL_STYLE: Record<string, string> = {
  ai_agent: "bg-trap/20 text-[#ffb3b3] border-trap/50", scanner: "bg-warn/15 text-warn border-warn/40",
  human: "bg-real/15 text-real border-real/40", unknown: "bg-white/5 text-text2 border-line",
};

function Row({ x, onPick, active }: { x: SessionData; onPick: (sid: string) => void; active: boolean }) {
  const stage = STAGES.indexOf(x.stage);
  return (
    <button onClick={() => onPick(x.session)}
      className={`w-full text-left px-3 py-2 border-b border-line hover:bg-white/5 ${active ? "bg-white/5" : ""}`}>
      <div className="flex items-center gap-2">
        <span className="w-2 h-2 rounded-full" style={{ background: sideColor(x.side) }} />
        <span className="font-mono text-sm" title={x.session}>{short(x.session)}</span>
        {x.raider && <span className="font-mono text-xs" style={{ color: agentColor(x.raider) }}>{x.raider}</span>}
        <span className={`ml-auto text-[11px] uppercase tracking-wider px-1.5 py-0.5 rounded border ${LABEL_STYLE[x.label] ?? LABEL_STYLE.unknown}`}>
          {x.label.replace("_", " ")}
        </span>
      </div>
      <div className="flex items-center gap-2 mt-1.5">
        <div className="h-1 w-16 bg-line rounded overflow-hidden" title={`confidence ${x.confidence ?? "-"}`}>
          <div className="h-full" style={{ width: `${Math.round((x.confidence ?? 0) * 100)}%`, background: "var(--text-2)" }} />
        </div>
        <div className="flex gap-0.5" title={`stage: ${x.stage}`}>
          {STAGES.slice(0, 6).map((st, i) => (
            <span key={st} className="w-1.5 h-1.5 rounded-full" style={{ background: i <= stage ? sideColor(x.side) : "var(--line)" }} />
          ))}
        </div>
        <span className="text-xs text-text2 ml-auto font-mono">
          {x.side === "real" ? "olympus" : x.side}{x.pod ? ` · ${x.pod}` : ""}{x.pace && x.pace !== "normal" ? ` · ${x.pace}` : ""} · risk {x.risk}
        </span>
      </div>
    </button>
  );
}

export function Sessions({ s, picked, onPick }: { s: State; picked: string | null; onPick: (sid: string) => void }) {
  const list = Object.values(s.sessions).filter((x) => !x.ended)
    .sort((a, b) => Number(b.side !== "real") - Number(a.side !== "real") || Number(!!b.raider) - Number(!!a.raider)
      || (b.last_seen ?? "").localeCompare(a.last_seen ?? ""));
  const trapped = list.filter((x) => x.side !== "real").length;
  return (
    <Panel title="Sessions" className="col-span-4" bodyClass="overflow-y-auto scroll-thin"
      right={<span className="text-xs text-text2">{list.length} live · <span style={{ color: "var(--trap)" }}>{trapped} trapped</span></span>}>
      {list.slice(0, 80).map((x) => <Row key={x.session} x={x} onPick={onPick} active={picked === x.session} />)}
      {!list.length && <p className="p-4 text-text2 text-sm">No visitors yet. Press “Release the swarm”.</p>}
    </Panel>
  );
}
