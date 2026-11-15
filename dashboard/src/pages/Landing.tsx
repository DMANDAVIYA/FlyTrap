import { ArrowRight } from "lucide-react";
import { useEffect } from "react";
import { Hero } from "@/components/landing/Hero";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { DolosMark, Wordmark } from "@/components/Logo";

export default function Landing() {
  useEffect(() => {
    document.title = "Dolos · a honeypot for rogue AI";
  }, []);

  return (
    <main className="relative">
      {/* Static film grain over the whole page. */}
      <div aria-hidden className="pointer-events-none fixed inset-0 z-50 bg-[url('/hero/grain.png')] opacity-[.055] mix-blend-screen" />

      <header className="absolute inset-x-0 top-0 z-30">
        <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 sm:px-8" aria-label="Main">
          <a href="#/" className="flex items-center gap-3" aria-label="Dolos home">
            <DolosMark />
            <Wordmark className="text-[13px]" />
          </a>
          <div className="flex items-center gap-6 sm:gap-8">
            <a href="#how" className="caps hidden text-[10.5px] text-text2 transition-colors hover:text-text sm:inline">How it works</a>
            <a href="#/console" className="btn btn-trap">Console <ArrowRight size={13} aria-hidden /></a>
          </div>
        </nav>
      </header>

      <Hero />
      <HowItWorks />

      <section className="mx-auto max-w-6xl px-5 pb-6 pt-16 sm:px-8">
        <p className="max-w-[24ch] font-display text-[clamp(2.25rem,5vw,4.25rem)] font-[250] uppercase leading-[.95] tracking-[0.02em]">
          The bot leaves with a full bag of fake data. <span className="text-green">Real records exposed: zero.</span>
        </p>
      </section>

      <section className="mt-16 border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col justify-between gap-10 px-5 py-20 sm:px-8 md:flex-row md:items-end">
          <div>
            <h2 className="font-display text-[clamp(3rem,7vw,6rem)] font-[200] uppercase leading-[.85] tracking-[0.03em]">See it happen live</h2>
            <p className="mt-5 max-w-[50ch] text-lg leading-relaxed text-text2">
              Release the test raiders and watch each one fall into Tartarus while real visitors stay on Olympus.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <a href="#/console" className="btn btn-trap !px-5 !py-3">Open the console <ArrowRight size={14} aria-hidden /></a>
            <a href="#/see" className="btn !px-5 !py-3">See what the bot sees <ArrowRight size={14} aria-hidden /></a>
          </div>
        </div>
        <footer className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-3 px-5 pb-10 text-[13px] text-text2 sm:px-8">
          <span className="flex items-center gap-2.5 text-text"><DolosMark size={20} /><Wordmark className="text-[12px]" /></span>
          <span><span className="font-display text-base tracking-[0.12em]">ΔΟΛΟΣ</span>, the Greek spirit of trickery.</span>
          <span>
            Hands: Michelangelo, <i>The Creation of Adam</i> (detail), public domain, via{" "}
            <a className="underline decoration-line2 hover:text-text" href="https://commons.wikimedia.org/wiki/File:Creation_of_Adam_(Michelangelo)_Detail.jpg" target="_blank" rel="noopener">Wikimedia Commons</a>
          </span>
          <span className="md:ml-auto">Built at HackUMass XIV</span>
        </footer>
      </section>
    </main>
  );
}
