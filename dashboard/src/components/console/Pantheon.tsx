import { Brain, Dog, Eye, Feather, Hammer, ScrollText, Shield, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { CardTitle, GlowCard } from "@/components/ui/glow-card";
import type { State } from "@/feed";
import { BLUE, ROLE } from "@/types";

const ICON: Record<string, LucideIcon> = {
  athena: Shield, argus: Eye, hephaestus: Hammer, cerberus: Dog, mnemosyne: Brain, clio: ScrollText, hermes: Feather,
};

/** The defending agents as a row of tiles. Hover, focus or tap one to read its job and state. */
export function Pantheon({ s, className = "" }: { s: State; className?: string }) {
  const [on, setOn] = useState<string | null>(null);
  const r = on ? s.roster[on] : undefined;
  const acting = BLUE.filter((n) => s.roster[n]?.state === "acting").length;
  return (
    <GlowCard label="Defending agents" className={className}>
      <CardTitle right={<span className="text-[12.5px] text-text2" aria-live="polite">{on ? <><span className="font-semibold capitalize text-text">{on}</span> · {ROLE[on]} · {r?.state ?? "watching"}{r?.mode === "rules" ? " (rules)" : ""}</> : `${acting} acting`}</span>}>
        Pantheon
      </CardTitle>
      <ul className="grid grid-cols-7 gap-1.5 sm:gap-2">
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
                onClick={() => setOn(name)}
                onBlur={() => setOn(null)}
                aria-label={`${name}: ${ROLE[name]}, ${st}`}
                className={`group flex w-full flex-col items-center gap-1.5 ${st === "offline" ? "opacity-50" : ""}`}
              >
                <span className={`relative grid aspect-square w-full max-w-[3rem] place-items-center rounded-[13px] border transition-colors ${
                  live ? "border-green/70 bg-green/10 text-green shadow-[0_0_18px_rgba(61,255,143,.25)]"
                    : on === name ? "border-text2/60 bg-inner text-text" : "border-line2/70 bg-inner text-text2 group-hover:text-text"}`}>
                  <Icon size={19} strokeWidth={1.7} aria-hidden />
                  {live && <span className="dolos-pulse absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-green" />}
                </span>
                <span className="w-full truncate text-center text-[10.5px] capitalize text-text2">{name}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </GlowCard>
  );
}
