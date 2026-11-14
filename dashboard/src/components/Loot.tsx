import type { State } from "../feed";
import { Panel, agentColor, short } from "./Panel";

export function Loot({ s }: { s: State }) {
  const raiderOf = (sid: string) => s.sessions[sid]?.raider ?? null;
  return (
    <Panel title="Trackers & campaigns" className="col-span-4" bodyClass="overflow-y-auto scroll-thin">
      <div className="p-3 space-y-2">
        {s.campaigns.map((c) => (
          <div key={c.id} className="rounded border border-trap/50 bg-trap/10 p-2.5">
            <div className="font-display font-semibold tracking-wider" style={{ color: "var(--trap)" }}>{c.name.toUpperCase()}</div>
            <div className="font-mono text-sm mt-1">
              {c.sessions.map((sid, i) => (
                <span key={sid}>{i > 0 && <span className="text-text2"> ⇄ </span>}
                  <span style={{ color: agentColor(raiderOf(sid) ?? "") }}>{raiderOf(sid) ?? short(sid)}</span>
                  {raiderOf(sid) && <span className="text-text2"> ({short(sid)})</span>}
                </span>
              ))}
            </div>
            <div className="text-xs text-text2 mt-1">{c.reason}{c.evidence?.length ? ` · evidence #${c.evidence.join(", #")}` : ""}</div>
          </div>
        ))}
        {s.canaries.slice().reverse().map((c, i) => (
          <div key={i} className="rounded border border-warn/40 bg-warn/5 p-2.5 font-mono text-sm">
            <div className="text-warn font-semibold">⚑ {c.kind.replace("_", " ")} used</div>
            <div className="text-text2 text-xs mt-0.5">
              shown to <span style={{ color: agentColor(raiderOf(c.planted_in) ?? "") }}>{raiderOf(c.planted_in) ?? short(c.planted_in)}</span>
              {" "}→ used by <span style={{ color: agentColor(raiderOf(c.used_by) ?? "") }}>{raiderOf(c.used_by) ?? short(c.used_by)}</span>
              {c.planted_in !== c.used_by && <span className="text-trap"> (cross-session)</span>} · event #{c.event_id}
            </div>
          </div>
        ))}
        {!s.campaigns.length && !s.canaries.length && (
          <p className="text-text2 text-sm">Every key shown inside Tartarus is unique to one visitor. When one is used, it shows up here.</p>
        )}
      </div>
    </Panel>
  );
}
