import { useState } from "react";
import { control, type State } from "../feed";
import { Panel } from "./Panel";

export function Approvals({ s }: { s: State }) {
  const [busy, setBusy] = useState<number | null>(null);
  const pending = Object.values(s.approvals).filter((a) => a.status === "pending");
  const decide = async (id: number, action: "approve" | "reject") => {
    setBusy(id);
    try { await control(`${action}/${id}`); } finally { setBusy(null); }
  };
  return (
    <Panel title="Zeus · approvals" className="col-span-3" bodyClass="overflow-y-auto scroll-thin"
      right={pending.length ? <span className="text-xs text-warn">{pending.length} waiting</span> : null}>
      <div className="p-3 space-y-2">
        {pending.map((a) => (
          <div key={a.id} className="rounded border border-warn/40 p-2.5">
            <div className="text-[11px] uppercase tracking-widest text-warn">{a.kind.replace("_", " ")} · #{a.id}</div>
            <div className="text-sm mt-1">{a.summary}</div>
            <div className="flex gap-2 mt-2">
              <button className="btn btn-ok !py-1" disabled={busy === a.id} onClick={() => decide(a.id, "approve")}>Approve</button>
              <button className="btn !py-1" disabled={busy === a.id} onClick={() => decide(a.id, "reject")}>Reject</button>
            </div>
          </div>
        ))}
        {!pending.length && <p className="text-text2 text-sm">Release, global rules and lockdown wait here for a human.</p>}
      </div>
    </Panel>
  );
}
