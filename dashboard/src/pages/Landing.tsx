import { ArrowRight, ArrowUpRight, ChevronDown } from "lucide-react";
import { useEffect } from "react";
import { DolosMark, Wordmark } from "@/components/Logo";

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

export default function Landing() {
  const bait = `${location.protocol}//${location.hostname}:8080`;

  useEffect(() => {
    document.title = "Dolos · a honeypot for rogue AI";
  }, []);

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

      <section className="flex min-h-[100svh] flex-col items-center justify-center px-5 text-center">
        <h1 className="font-display text-[clamp(6rem,20vw,16rem)] font-[200] leading-none tracking-[0.06em]">DOLOS</h1>
        <p className="mt-6 max-w-[36ch] text-lg">A honeypot for rogue AI that hides inside your real website.</p>
        <a href="#/console" className="btn btn-trap mt-8">Open the console <ArrowRight size={14} aria-hidden /></a>
        <a href="#how" className="caps mt-12 flex flex-col items-center gap-1 text-[10.5px] text-text2 hover:text-text">How it works <ChevronDown size={16} aria-hidden /></a>
      </section>

      <section id="how" className="mx-auto max-w-6xl px-5 sm:px-8 pt-20 pb-24 scroll-mt-4">
        <h2 className="font-semibold text-[clamp(2.25rem,5vw,3.75rem)] leading-[1.02] tracking-[-0.02em]">How it works</h2>
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
              <h3 className="font-semibold text-xl sm:text-2xl leading-tight">{s.name}</h3>
              <p className="text-[17px] leading-relaxed text-real">
                <span className="md:hidden mr-2 text-[11px] font-bold uppercase tracking-[0.2em] text-real">They see</span>
                {s.see}
              </p>
              <p className="font-mono text-[15px] leading-relaxed text-text md:border-l md:border-line md:pl-10">
                <span className="md:hidden mr-2 text-[11px] font-bold uppercase tracking-[0.2em] text-trap">Really</span>
                {s.real}
              </p>
            </li>
          ))}
        </ol>
        <div className="border-t border-line pt-12">
          <p className="font-semibold text-[clamp(1.5rem,3.4vw,2.6rem)] leading-[1.12] max-w-[30ch]">
            The bot leaves with a full bag of fake data. <span className="text-green">Real records exposed: zero.</span>
          </p>
        </div>
      </section>

      <section className="border-t border-line">
        <div className="mx-auto max-w-6xl px-5 sm:px-8 py-20 sm:py-24 flex flex-col md:flex-row md:items-end justify-between gap-10">
          <div>
            <h2 className="font-semibold text-[clamp(2.25rem,5.5vw,4.25rem)] leading-none tracking-[-0.02em]">Take the red pill.</h2>
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
