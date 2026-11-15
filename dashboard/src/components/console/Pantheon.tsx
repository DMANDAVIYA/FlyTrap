import { Brain, Dog, Eye, Feather, Hammer, ScrollText, Shield, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { CardTitle, GlowCard } from "@/components/ui/glow-card";
import type { State } from "@/feed";
import { BLUE, ROLE } from "@/types";

const ICON: Record<string, LucideIcon> = {
  athena: Shield, argus: Eye, hephaestus: Hammer, cerberus: Dog, mnemosyne: Brain, clio: ScrollText, hermes: Feather,
};

/** The defending agents. Hover or focus one to read its job and state. */
export function Pantheon({ s, className = "" }: { s: State; className?: string }) {
  const [on, setOn] = useState<string | null>(null);
  const r = on ? s.roster[on] : undefined;
  return (
    <GlowCard label="Defending agents" className={className}>
      <CardTitle>Pantheon</CardTitle>
      <ul className="grid grid-cols-4 gap-2">
        {BLUE.map((name) => {
          const Icon = ICON[name];
          const st = s.roster[name]?.state ?? "watching";
          const live = st === "acting";
          return (
            <li key={name}>
              <button
                type="button"
                onMouseEnter={() => setOn(name)}
                onMouseLeave={() => setOn(null)}
                onFocus={() => setOn(name)}
                onBlur={() => setOn(null)}
                aria-label={`${name}: ${ROLE[name]}, ${st}`}
                className={`relative flex w-full flex-col items-center gap-1 rounded-xl border px-1 py-2 transition-colors ${
                  on === name ? "border-green/60 bg-green/10 text-green" : "border-line2/70 text-text2 hover:text-text"
                } ${st === "offline" ? "opacity-50" : ""}`}
              >
                <Icon size={18} strokeWidth={1.7} aria-hidden />
                <span className="w-full truncate text-center text-[10px] font-semibold capitalize">{name}</span>
                {live && <span className="dolos-pulse absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-green" />}
              </button>
            </li>
          );
        })}
      </ul>
      <p className="mt-auto pt-3 text-xs leading-snug text-text2" aria-live="polite">
        {on ? (
          <><span className="font-semibold capitalize text-text">{on}</span> · {ROLE[on]} · {r?.state ?? "watching"}{r?.mode === "rules" ? " (rules mode)" : ""}</>
        ) : "Hover or tab to an agent to see its job."}
      </p>
    </GlowCard>
  );
}
