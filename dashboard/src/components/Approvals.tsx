import { Zap } from "lucide-react";
import { useState } from "react";
import { GlowCard } from "@/components/ui/glow-card";
import { control, type State } from "../feed";

/** Zeus: only takes space while a drastic action waits for a human. */
export function Approvals({ s, className = "" }: { s: State; className?: string }) {
  const [busy, setBusy] = useState<number | null>(null);
  const pending = Object.values(s.approvals).filter((a) => a.status === "pending");
  if (!pending.length) return null;

  const decide = async (id: number, action: "approve" | "reject") => {
    setBusy(id);
    try { await control(`${action}/${id}`); } finally { setBusy(null); }
  };

  return (
    <GlowCard label="Waiting for Zeus" glow="var(--warn-rgb)" className={className}>
      <ul className="flex flex-col gap-3">
        {pending.map((a) => (
          <li key={a.id} className="flex flex-wrap items-center gap-x-5 gap-y-2">
            <span className="caps flex items-center gap-2 text-[10.5px] font-bold text-warn">
              <Zap size={14} aria-hidden /> Zeus · {a.kind.replace("_", " ")} #{a.id}
            </span>
            <p className="min-w-[16rem] flex-1 text-sm leading-snug">{a.summary}</p>
            <div className="flex gap-2">
              <button className="btn btn-ok !py-1.5" disabled={busy === a.id} onClick={() => decide(a.id, "approve")}>Approve</button>
              <button className="btn !py-1.5" disabled={busy === a.id} onClick={() => decide(a.id, "reject")}>Reject</button>
            </div>
          </li>
        ))}
      </ul>
    </GlowCard>
  );
}
