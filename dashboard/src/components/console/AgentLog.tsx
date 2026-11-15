import { ArrowRight } from "lucide-react";
import { CardTitle, GlowCard } from "@/components/ui/glow-card";
import type { StreamItem } from "@/types";
import { KindIcon, agentColor, clock, short } from "../Panel";

/** The latest lines of one swarm, newest at the bottom. The drawer holds the full streams. */
export function AgentLog({ title, items, empty, onOpen, className = "" }: {
  title: string; items: StreamItem[]; empty: string; onOpen: () => void; className?: string;
}) {
  const lines = items.slice(-14);
  return (
    <GlowCard label={title} className={className}>
      <CardTitle right={
        <button onClick={onOpen} title="All streams" className="-m-1.5 flex items-center rounded-full p-1.5 text-text2 hover:text-text">
          <span className="sr-only">All streams</span>
          <ArrowRight size={14} aria-hidden />
        </button>
      }>
        {title}
      </CardTitle>
      <div role="log" aria-label={title} className="flex min-h-0 flex-1 flex-col justify-end gap-1.5 overflow-hidden font-mono text-[12.5px] leading-relaxed">
        {lines.map((it) => (
          <div key={`${it.t}-${it.agent}-${it.text}`} className="dolos-slide flex gap-2">
            <span className="shrink-0 tabular text-text2/70">{clock(it.t)}</span>
            <span className="min-w-0 [overflow-wrap:anywhere]">
              <span className="font-semibold uppercase" style={{ color: agentColor(it.agent) }}>{it.agent}</span>
              {it.session && it.session !== "-" && <span className="text-text2"> [{short(it.session)}]</span>}
               <KindIcon kind={it.kind} className={it.kind === "alert" ? "text-warn" : "text-text2"} />
              <span className="text-text/90">{it.text}</span>
            </span>
          </div>
        ))}
        {!lines.length && <p className="font-sans text-sm text-text2">{empty}</p>}
      </div>
    </GlowCard>
  );
}
