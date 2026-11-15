import type { State } from "../feed";
import type { SessionData } from "../types";
import { agentColor, short } from "./Panel";

const LABEL_STYLE: Record<string, string> = {
  ai_agent: "bg-trap/15 text-[#ffb3c0] border-trap/50", scanner: "bg-warn/10 text-warn border-warn/40",
  human: "bg-real/10 text-real border-real/40", unknown: "text-text2 border-line2",
};

function Row({ x, onPick, active }: { x: SessionData; onPick: (sid: string) => void; active: boolean }) {
  return (
    <li>
      <button
        onClick={() => onPick(x.session)}
        title={`${x.session}: open the incident report`}
        className={`w-full text-left px-4 py-2.5 border-b border-line transition-colors hover:bg-text/[.04] ${active ? "bg-text/[.05]" : ""} ${x.ended ? "opacity-55" : ""}`}
      >
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 shrink-0 rounded-full bg-trap" />
          {x.raider
            ? <span className="expanded text-sm font-semibold capitalize" style={{ color: agentColor(x.raider) }}>{x.raider}</span>
            : <span className="font-mono text-sm">{short(x.session)}</span>}
          <span className={`ml-auto rounded-[3px] border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${LABEL_STYLE[x.label] ?? LABEL_STYLE.unknown}`}>
            {x.label.replace("_", " ")}
          </span>
        </div>
        <div className="mt-1 flex gap-2 pl-4 font-mono text-[11.5px] text-text2">
          {x.raider && <span>{short(x.session)}</span>}
          <span>{x.side === "blocked" ? "blocked" : x.pod ?? "tartarus"}</span>
          <span>· {x.ended ? "left" : x.stage}</span>
        </div>
      </button>
    </li>
  );
}

/** Trapped visitors only; real visitors are counted, not listed. Click opens the report. */
export function Sessions({ s, picked, onPick }: { s: State; picked: string | null; onPick: (sid: string) => void }) {
  const all = Object.values(s.sessions);
  const onOlympus = all.filter((x) => !x.ended && x.side === "real").length;
  // Ended sessions stay listed (dimmed) so the list matches the Trapped count.
  const trapped = all.filter((x) => x.side !== "real")
    .sort((a, b) => Number(!!a.ended) - Number(!!b.ended) || Number(!!b.raider) - Number(!!a.raider)
      || (b.last_seen ?? "").localeCompare(a.last_seen ?? ""));
  return (
    <section aria-label="Trapped visitors" className="flex min-h-0 flex-1 flex-col">
      <header className="flex items-baseline justify-between border-b border-line px-4 py-2.5">
        <h2 className="panel-title">Trapped visitors</h2>
        <span className="text-xs text-text2">{onOlympus} on Olympus</span>
      </header>
      {trapped.length ? (
        <ul className="flex-1 min-h-0 overflow-y-auto scroll-thin">
          {trapped.slice(0, 80).map((x) => <Row key={x.session} x={x} onPick={onPick} active={picked === x.session} />)}
        </ul>
      ) : (
        <p className="px-4 py-5 text-sm text-text2">No one trapped yet. Press Release the swarm to start the raiders.</p>
      )}
    </section>
  );
}
