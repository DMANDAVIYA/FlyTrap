import { useState } from "react";
import { control, type State } from "../feed";

/** Zeus: only takes space while a drastic action waits for a human. */
export function Approvals({ s }: { s: State }) {
  const [busy, setBusy] = useState<number | null>(null);
  const pending = Object.values(s.approvals).filter((a) => a.status === "pending");
  if (!pending.length) return null;

  const decide = async (id: number, action: "approve" | "reject") => {
    setBusy(id);
    try { await control(`${action}/${id}`); } finally { setBusy(null); }
  };

  return (
    <section aria-label="Waiting for Zeus" className="border-b border-line bg-warn/[.06] px-4 py-3">
      <h2 className="panel-title !text-warn">Zeus · {pending.length} waiting</h2>
      <ul className="mt-2 space-y-3 max-h-60 overflow-y-auto scroll-thin">
        {pending.map((a) => (
          <li key={a.id}>
            <div className="text-[11px] font-semibold uppercase tracking-widest text-warn/80">{a.kind.replace("_", " ")} · #{a.id}</div>
            <p className="mt-0.5 text-sm leading-snug">{a.summary}</p>
            <div className="mt-2 flex gap-2">
              <button className="btn btn-ok !py-1" disabled={busy === a.id} onClick={() => decide(a.id, "approve")}>Approve</button>
              <button className="btn !py-1" disabled={busy === a.id} onClick={() => decide(a.id, "reject")}>Reject</button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
