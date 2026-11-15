import { CardTitle, GlowCard, useAnimatedNumber } from "@/components/ui/glow-card";
import type { State } from "@/feed";
import { short } from "../Panel";

/** What the attackers walked away with: fake records, and the marked keys they went on to use. */
export function Taken({ s, className = "" }: { s: State; className?: string }) {
  const fake = useAnimatedNumber(s.stats.fake_records_taken);
  const who = (sid: string) => s.sessions[sid]?.raider ?? short(sid);
  const recent = s.canaries.slice(-1);
  return (
    <GlowCard label="What they took" className={className}>
      <CardTitle right={<span className="text-xs text-text2">{s.campaigns.length} {s.campaigns.length === 1 ? "campaign" : "campaigns"}</span>}>
        What they took
      </CardTitle>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="font-display text-[clamp(2.5rem,3.4vw,3.5rem)] font-[300] leading-[.82] tabular text-green">{Math.round(fake)}</div>
          <div className="caps mt-2 text-[10px] text-text2">fake records</div>
        </div>
        <div>
          <div className="font-display text-[clamp(2.5rem,3.4vw,3.5rem)] font-[300] leading-[.82] tabular text-text">{s.stats.canaries_fired}</div>
          <div className="caps mt-2 text-[10px] text-text2">marked keys used</div>
        </div>
      </div>
      {recent.length ? (
        <ul className="mt-auto min-h-0 space-y-1 overflow-hidden pt-3 font-mono text-[11.5px] leading-snug text-text2">
          {recent.map((c) => (
            <li key={c.event_id} className="truncate">
              <span className="text-green">{c.kind.replace("_", " ")}</span> shown to <span className="text-text">{who(c.planted_in)}</span>, used by{" "}
              <span className="text-text">{who(c.used_by)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-auto pt-3 text-xs leading-snug text-text2">Every key shown in Tartarus is unique to one visitor. When one is used, it names the visitor here.</p>
      )}
    </GlowCard>
  );
}
