import { ArrowLeft, ArrowRight } from "lucide-react";
import { useEffect } from "react";
import { DolosMark, Wordmark } from "@/components/Logo";
import { CompareFlow, STEPS } from "@/components/see/CompareFlow";

/** "See what the bot sees": one window, two worlds, a bar to drag between them. */
export default function BotView() {
  useEffect(() => {
    document.title = "Dolos · what the bot sees";
  }, []);

  return (
    <main className="relative min-h-[100svh]">
      <div aria-hidden className="pointer-events-none fixed inset-0 z-50 bg-[url('/hero/grain.png')] opacity-[.055] mix-blend-screen" />

      <header>
        <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 sm:px-8" aria-label="Main">
          <a href="#/" className="flex items-center gap-3" aria-label="Dolos home">
            <DolosMark />
            <Wordmark className="text-[13px]" />
          </a>
          <div className="flex items-center gap-6 sm:gap-8">
            <a href="#/" className="caps hidden items-center gap-1.5 text-[10.5px] text-text2 transition-colors hover:text-text sm:flex">
              <ArrowLeft size={13} aria-hidden /> Home
            </a>
            <a href="#/console" className="btn btn-trap">Console <ArrowRight size={13} aria-hidden /></a>
          </div>
        </nav>
      </header>

      <section aria-labelledby="see-title" className="mx-auto max-w-6xl px-5 pb-20 pt-10 sm:px-8 sm:pt-14">
        <h1 id="see-title" className="font-display text-[clamp(3.25rem,8vw,7rem)] font-[200] uppercase leading-[.85] tracking-[0.03em]">
          What the bot sees
        </h1>
        <p className="mb-8 mt-5 max-w-[62ch] text-lg leading-relaxed text-text2">
          One website, two worlds. Drag the line: to the left, what really happens; to the right, what the bot sees. The bot walks the five steps live.
        </p>
        <CompareFlow />
        <ol className="sr-only">
          {STEPS.map((s) => <li key={s.name}>{s.name}. They see: {s.see} What really happens: {s.real}</li>)}
        </ol>

        <div className="mt-14 flex flex-wrap items-center gap-3 border-t border-line pt-10">
          <a href="#/console" className="btn btn-trap !px-5 !py-3">Watch it live in the console <ArrowRight size={14} aria-hidden /></a>
        </div>
      </section>
    </main>
  );
}
