import { ArrowRight, ArrowUpRight, ChevronDown } from "lucide-react";
import { lazy, Suspense, useEffect, useState } from "react";
import { DolosMark, Wordmark } from "@/components/Logo";
import { Scramble } from "@/components/Scramble";
import type { PillId } from "@/components/three/Pills";
import RainingLetters from "@/components/ui/modern-animated-hero-section";

const Pills = lazy(() => import("@/components/three/Pills"));

// Plain-words version of the README's five steps. No numbers it does not state.
const STEPS = [
  {
    name: "The front door",
    see: "A normal website. Pages load, the login works.",
    real: "Every request passes Charon, our gateway. It decides with simple rules in memory, so there is no AI in the way and no visible delay.",
  },
  {
    name: "The bait",
    see: "A leaked password file, a hidden admin link, an old backup nobody cleaned up.",
    real: "Tripwires. Real customers never see them. Only scripts and AI agents snooping around find them.",
  },
  {
    name: "The switch",
    see: "Nothing changes. Same pages, same login, plenty of data to steal.",
    real: "They now live in Tartarus: their own copy of the site, same code, fake data. There is no route back to the real servers.",
  },
  {
    name: "The loot",
    see: "API keys and tokens, ready to use.",
    real: "Every key is unique to one visitor. The moment one is used, it names who took it and links everyone who shares it.",
  },
  {
    name: "The watchers",
    see: "Maybe a slow page or two.",
    real: "Sixteen defending AI agents label each visitor as human, scanner or AI agent, slow it down and write the incident report. Big moves wait for Zeus: a human.",
  },
];

function PillChoice({ id, href, title, line, hint, active, onHover }: {
  id: PillId; href: string; title: string; line: string; hint: string; active: boolean; onHover: (p: PillId | null) => void;
}) {
  const blue = id === "blue";
  const Icon = blue ? ArrowUpRight : ArrowRight;
  return (
    <a
      href={href}
      target={blue ? "_blank" : undefined}
      rel={blue ? "noopener" : undefined}
      onMouseEnter={() => onHover(id)}
      onMouseLeave={() => onHover(null)}
      onFocus={() => onHover(id)}
      onBlur={() => onHover(null)}
      className={`flex flex-col items-center text-center rounded-[3px] border px-3 py-3 sm:px-5 transition-colors ${
        blue
          ? active ? "border-real bg-real/10" : "border-real/35"
          : active ? "border-trap bg-trap/10" : "border-trap/45"
      }`}
    >
      <span className={`font-mono text-[11px] font-bold uppercase tracking-[0.24em] ${blue ? "text-real" : "text-trap"}`}>{title}</span>
      <span className="mt-1.5 expanded text-base sm:text-lg font-semibold leading-tight">{line}</span>
      <span className="mt-1 text-sm text-text2 hidden sm:inline-flex items-center gap-1">
        {hint} <Icon size={14} aria-hidden />
      </span>
    </a>
  );
}

export default function Landing() {
  const [hover, setHover] = useState<PillId | null>(null);
  const bait = `${location.protocol}//${location.hostname}:8080`;

  useEffect(() => {
    document.title = "Dolos · a honeypot for rogue AI";
  }, []);

  const pick = (p: PillId) => {
    if (p === "red") location.hash = "#/console";
    else window.open(bait, "_blank", "noopener");
  };

  return (
    <main>
      <header className="absolute inset-x-0 top-0 z-30">
        <nav className="mx-auto max-w-6xl px-5 sm:px-8 h-16 flex items-center justify-between" aria-label="Main">
          <a href="#/" className="flex items-center gap-2.5" aria-label="Dolos home">
            <DolosMark />
            <Wordmark className="text-[15px]" />
          </a>
          <div className="flex items-center gap-5 sm:gap-7 text-sm">
            <a href="#how" className="hidden sm:inline text-text2 hover:text-text transition-colors">How it works</a>
            <a href="#/console" className="btn btn-trap">Console <ArrowRight size={14} aria-hidden /></a>
          </div>
        </nav>
      </header>

      <RainingLetters phrases={["DOLOS", "ΔΟΛΟΣ"]} label="Dolos">
        <p className="mt-7 max-w-[30ch] text-center expanded font-semibold text-[clamp(1.25rem,2.6vw,1.75rem)] leading-[1.2] text-balance">
          A honeypot for rogue AI that hides inside your real website.
        </p>
        <p className="mt-4 max-w-[52ch] text-center text-text2 text-[15px] sm:text-base leading-relaxed text-balance">
          Bots that touch the bait are quietly moved into a perfect copy of the site, filled with fake data. They never find out.
        </p>

        <div className="mt-6 w-[min(720px,94vw)]">
          <div className="relative h-[190px] sm:h-[230px]">
            <Suspense fallback={null}>
              <Pills hovered={hover} onHover={setHover} onPick={pick} />
            </Suspense>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:gap-6">
            <PillChoice id="blue" href={bait} title="Blue pill" line="Stay in the illusion" hint="See the site as a bot does"
              active={hover === "blue"} onHover={setHover} />
            <PillChoice id="red" href="#/console" title="Red pill" line="See the truth" hint="Open the live console"
              active={hover === "red"} onHover={setHover} />
          </div>
        </div>

        <a href="#how" className="mt-12 flex flex-col items-center gap-1 text-[11px] uppercase tracking-[0.24em] text-text2 hover:text-text transition-colors">
          How it works <ChevronDown size={16} aria-hidden />
        </a>
      </RainingLetters>

      <section id="how" className="mx-auto max-w-6xl px-5 sm:px-8 pt-20 pb-24 scroll-mt-4">
        <h2 className="expanded font-semibold text-[clamp(2.25rem,5vw,3.75rem)] leading-[1.02] tracking-[-0.02em]">How it works</h2>
        <p className="mt-5 max-w-[56ch] text-lg leading-relaxed text-text2">
          One website, two worlds. Every step has two sides: what the attacker sees, and what really happens.
        </p>

        <div className="mt-14 hidden md:grid grid-cols-[minmax(0,0.75fr)_minmax(0,1fr)_minmax(0,1.2fr)] gap-x-10 pb-4 text-[11px] font-bold uppercase tracking-[0.24em]">
          <span />
          <span className="flex items-center gap-2 text-real"><span className="h-2 w-2 rounded-full bg-real" />What they see</span>
          <span className="flex items-center gap-2 text-trap pl-10"><span className="h-2 w-2 rounded-full bg-trap" />What really happens</span>
        </div>
        <ol className="mt-8 md:mt-0">
          {STEPS.map((s) => (
            <li key={s.name} className="grid md:grid-cols-[minmax(0,0.75fr)_minmax(0,1fr)_minmax(0,1.2fr)] gap-x-10 gap-y-3 border-t border-line py-8">
              <h3 className="expanded font-semibold text-xl sm:text-2xl leading-tight">{s.name}</h3>
              <p className="text-[17px] leading-relaxed text-[#c9dcff]">
                <span className="md:hidden mr-2 text-[11px] font-bold uppercase tracking-[0.2em] text-real">They see</span>
                {s.see}
              </p>
              <p className="font-mono text-[15px] leading-relaxed text-[#ffc2cc] md:border-l md:border-line md:pl-10">
                <span className="md:hidden mr-2 text-[11px] font-bold uppercase tracking-[0.2em] text-trap">Really</span>
                <Scramble text={s.real} onView />
              </p>
            </li>
          ))}
        </ol>
        <div className="border-t border-line pt-12">
          <p className="expanded font-semibold text-[clamp(1.5rem,3.4vw,2.6rem)] leading-[1.12] max-w-[30ch]">
            The bot leaves with a full bag of fake data. <span className="text-matrix">Real records exposed: zero.</span>
          </p>
        </div>
      </section>

      <section className="border-t border-line">
        <div className="mx-auto max-w-6xl px-5 sm:px-8 py-20 sm:py-24 flex flex-col md:flex-row md:items-end justify-between gap-10">
          <div>
            <h2 className="expanded font-semibold text-[clamp(2.25rem,5.5vw,4.25rem)] leading-none tracking-[-0.02em]">Take the red pill.</h2>
            <p className="mt-5 max-w-[50ch] text-lg leading-relaxed text-text2">
              Release the test raiders and watch each one fall into Tartarus while real visitors stay on Olympus.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <a href="#/console" className="btn btn-trap !text-[13px] !px-5 !py-3">Open the console <ArrowRight size={15} aria-hidden /></a>
            <a href={bait} target="_blank" rel="noopener" className="btn !text-[13px] !px-5 !py-3">Visit the bait site <ArrowUpRight size={15} aria-hidden /></a>
          </div>
        </div>
        <footer className="mx-auto max-w-6xl px-5 sm:px-8 pb-10 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-text2">
          <span className="flex items-center gap-2 text-text"><DolosMark size={22} /><Wordmark className="text-[13px]" /></span>
          <span><span className="font-mono">ΔΟΛΟΣ</span>, the Greek spirit of trickery.</span>
          <span className="md:ml-auto">Built at HackUMass XIV</span>
        </footer>
      </section>
    </main>
  );
}
