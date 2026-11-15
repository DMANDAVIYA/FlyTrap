import { CardTitle, GlowCard } from "@/components/ui/glow-card";
import type { State } from "../feed";
import type { SessionData } from "../types";
import { agentColor, short } from "./Panel";

const LABEL_STYLE: Record<string, string> = {
  ai_agent: "bg-trap/10 text-trap border-trap/45", scanner: "text-real border-real/40",
  human: "text-text2 border-line2", unknown: "text-text2/70 border-line",
};

function Row({ x, onPick, active }: { x: SessionData; onPick: (sid: string) => void; active: boolean }) {
  return (
    <li>
      <button
        onClick={() => onPick(x.session)}
        title={`${x.session}: open the incident report`}
        className={`w-full border-b border-line/80 py-2.5 text-left transition-colors hover:bg-text/[.03] ${active ? "bg-text/[.05]" : ""} ${x.ended ? "opacity-55" : ""}`}
      >
        <div className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-trap" />
          {x.raider
            ? <span className="text-sm font-semibold capitalize" style={{ color: agentColor(x.raider) }}>{x.raider}</span>
            : <span className="font-mono text-sm">{short(x.session)}</span>}
          <span className={`ml-auto rounded-full border px-2 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.14em] ${LABEL_STYLE[x.label] ?? LABEL_STYLE.unknown}`}>
            {x.label.replace("_", " ")}
          </span>
        </div>
        <div className="mt-1 flex gap-2 pl-3.5 font-mono text-[11.5px] text-text2">
          {x.raider && <span>{short(x.session)}</span>}
          <span>{x.side === "blocked" ? "blocked" : x.pod ?? "tartarus"}</span>
          <span>· {x.ended ? "left" : x.stage}</span>
        </div>
      </button>
    </li>
  );
}

/** Trapped visitors only; real visitors are counted, not listed. Click opens the report. */
export function Sessions({ s, picked, onPick, className = "" }: { s: State; picked: string | null; onPick: (sid: string) => void; className?: string }) {
  const all = Object.values(s.sessions);
  const onOlympus = all.filter((x) => !x.ended && x.side === "real").length;
  // Ended sessions stay listed (dimmed) so the list matches the Trapped count.
  const trapped = all.filter((x) => x.side !== "real")
    .sort((a, b) => Number(!!a.ended) - Number(!!b.ended) || Number(!!b.raider) - Number(!!a.raider)
      || (b.last_seen ?? "").localeCompare(a.last_seen ?? ""));
  return (
    <GlowCard label="Trapped visitors" className={className}>
      <CardTitle right={<span className="text-xs text-text2">{onOlympus} on Olympus</span>}>Trapped visitors</CardTitle>
      {trapped.length ? (
        <ul className="-mx-1 min-h-0 flex-1 overflow-y-auto px-1 scroll-thin">
          {trapped.slice(0, 80).map((x) => <Row key={x.session} x={x} onPick={onPick} active={picked === x.session} />)}
        </ul>
      ) : (
        <p className="text-sm leading-relaxed text-text2">
          {s.stats.trapped
            ? "No trapped visitor is active right now. Past sessions and their reports are under Details."
            : "No one trapped yet. Press Release the swarm to start the raiders."}
        </p>
      )}
    </GlowCard>
  );
}
