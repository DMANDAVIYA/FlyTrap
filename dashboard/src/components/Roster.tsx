import type { State } from "../feed";
import { BLUE, RED, ROLE } from "../types";
import { Panel, agentColor } from "./Panel";

function Who({ name, s }: { name: string; s: State }) {
  const r = s.roster[name];
  const st = r?.state ?? (RED.includes(name as never) ? "idle" : "watching");
  const live = st === "acting" || st === "attacking";
  return (
    <div className="flex items-center gap-2 leading-[22px]" title={`${name}: ${ROLE[name]}`}>
      <span className={`w-2 h-2 shrink-0 rounded-full ${live ? "animate-pulse" : ""}`}
        style={{ background: st === "offline" ? "#3a4450" : agentColor(name), boxShadow: live ? `0 0 8px ${agentColor(name)}` : "none" }} />
      <span className="font-display font-semibold uppercase tracking-wider text-[13px] flex-1 truncate" style={{ color: agentColor(name) }}>{name}</span>
      <span className={`text-[10px] uppercase ${st === "offline" ? "text-text2/60 line-through" : live ? "text-text" : "text-text2"}`}>
        {st === "offline" ? "offline" : st}{r?.mode === "rules" ? " ·rules" : ""}
      </span>
    </div>
  );
}

export function Roster({ s }: { s: State }) {
  return (
    <Panel title="Swarm roster" bodyClass="overflow-y-auto scroll-thin px-3 py-2 grid grid-cols-2 gap-x-4 content-start">
      <div>
        <div className="text-[10px] uppercase tracking-widest text-real mb-0.5">Blue · defenders</div>
        {BLUE.map((a) => <Who key={a} name={a} s={s} />)}
      </div>
      <div>
        <div className="text-[10px] uppercase tracking-widest text-trap mb-0.5">Red · raiders</div>
        {RED.map((a) => <Who key={a} name={a} s={s} />)}
        <div className="text-[10px] text-text2 mt-1 leading-tight">offline = AI down, rules still active</div>
      </div>
    </Panel>
  );
}
