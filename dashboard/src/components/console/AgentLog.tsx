import { ArrowRight } from "lucide-react";
import { CardTitle, GlowCard } from "@/components/ui/glow-card";
import type { State } from "@/feed";
import { agentColor, clock, short } from "../Panel";

const MARK: Record<string, string> = { thought: "›", action: "⚙", note: "✎", alert: "!" };

/** Latest lines from both swarms, newest at the bottom. The drawer holds the full streams. */
export function AgentLog({ s, onOpen, className = "" }: { s: State; onOpen: () => void; className?: string }) {
  const lines = [...s.red.slice(-30), ...s.blue.slice(-30)].sort((a, b) => a.t - b.t).slice(-14);
  return (
    <GlowCard label="Agent messages" className={className}>
      <CardTitle right={
        <button onClick={onOpen} className="caps flex items-center gap-1.5 text-[10px] text-text2 hover:text-text">
          All streams <ArrowRight size={12} aria-hidden />
        </button>
      }>
        Messages
      </CardTitle>
      <div role="log" aria-label="Latest agent messages" className="flex min-h-0 flex-1 flex-col justify-end gap-1.5 overflow-hidden font-mono text-[12.5px] leading-relaxed">
        {lines.map((it) => (
          <div key={`${it.t}-${it.agent}-${it.text}`} className="dolos-slide flex gap-2">
            <span className="shrink-0 tabular text-text2/70">{clock(it.t)}</span>
            <span className="min-w-0 [overflow-wrap:anywhere]">
              <span className="font-semibold uppercase" style={{ color: agentColor(it.agent) }}>{it.agent}</span>
              {it.session && it.session !== "-" && <span className="text-text2"> [{short(it.session)}]</span>}
              <span className="text-text2"> {MARK[it.kind]} </span>
              <span className={it.kind === "alert" ? "text-warn" : "text-text/90"}>{it.text}</span>
            </span>
          </div>
        ))}
        {!lines.length && <p className="font-sans text-sm text-text2">Hermes carries every agent's message here once the swarm is released.</p>}
      </div>
    </GlowCard>
  );
}
