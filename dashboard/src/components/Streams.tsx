import { useEffect, useRef } from "react";
import type { StreamItem } from "../types";
import { Panel, agentColor, clock, short } from "./Panel";

// Follow the newest line unless the operator scrolled up to read.
function useStick(dep: unknown) {
  const ref = useRef<HTMLDivElement>(null);
  const stuck = useRef(true);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onScroll = () => { stuck.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40; };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);
  useEffect(() => {
    const el = ref.current;
    if (el && stuck.current) el.scrollTop = el.scrollHeight;
  }, [dep]);
  return ref;
}

const MARK: Record<string, string> = { thought: "›", action: "⚙", note: "✎", alert: "!" };

function Line({ it }: { it: StreamItem }) {
  const rejected = it.kind === "action" && it.status === "rejected";
  const pending = it.kind === "action" && it.status === "pending_approval";
  const alert = it.kind === "alert";
  return (
    <div className={`px-3 py-1.5 font-mono text-[13px] leading-snug border-b border-line/50 ${alert ? "bg-warn/10" : ""}`}>
      <span className="text-text2 mr-2 tabular-nums">{clock(it.t)}</span>
      <span className="font-semibold uppercase mr-1" style={{ color: agentColor(it.agent) }}>{it.agent}</span>
      {it.session && it.session !== "-" && <span className="text-text2 mr-1" title={it.session}>[{short(it.session)}]</span>}
      <span className="text-text2 mr-1">{MARK[it.kind]}</span>
      <span className={rejected ? "text-trap line-through decoration-trap/40" : pending ? "text-warn" : "text-text"}>{it.text}</span>
      {rejected && <span className="ml-2 text-[11px] text-trap no-underline">policy guard</span>}
      {pending && <span className="ml-2 text-[11px] text-warn">awaiting Zeus</span>}
    </div>
  );
}

export function Stream({ title, items, color, empty }: { title: string; items: StreamItem[]; color: string; empty: string }) {
  const ref = useStick(items.length);
  return (
    <Panel title={title} className="col-span-4" right={<span className="w-2 h-2 rounded-full" style={{ background: color }} />}>
      <div ref={ref} className="h-full overflow-y-auto scroll-thin">
        {items.map((it, i) => <Line key={i} it={it} />)}
        {!items.length && <p className="p-4 text-text2 text-sm">{empty}</p>}
      </div>
    </Panel>
  );
}
