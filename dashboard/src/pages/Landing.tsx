import { ArrowRight } from "lucide-react";
import { useEffect } from "react";
import { Hero } from "@/components/landing/Hero";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { DolosMark, Wordmark } from "@/components/Logo";
import WildHuntFooter from "@/components/ui/wild-hunt-footer";

const CREDIT = "https://commons.wikimedia.org/wiki/File:Creation_of_Adam_(Michelangelo)_Detail.jpg";

export default function Landing() {
  const bait = `${location.protocol}//${location.hostname}:8080`;
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
      </section>

      <WildHuntFooter
        wordmark="DOLOS"
        image={{
          src: "/hero/footer-hands.webp",
          cutout: "/hero/footer-hands-cutout.webp",
          position: "50% 50%",
          alt: "A skeletal hand and Hermes' hand reaching for a glowing .env vial, toned green",
        }}
        preset="ink"
        palette={{ background: "#030604", ink: "#3dff8f" }}
        tagline="A honeypot for rogue AI · hidden inside your real website"
        sideNote="Built at HackUMass XIV · Olympus above · Tartarus below"
        columns={[
          { title: "Explore", links: [{ label: "How it works", href: "#how" }, { label: "What the bot sees", href: "#/see" }, { label: "Live console", href: "#/console" }] },
          { title: "Try it", links: [{ label: "Release the swarm", href: "#/console" }, { label: "Open the bait site", href: bait }] },
          { title: "Credits", links: [{ label: "Hero: The Creation of Adam", href: CREDIT }, { label: "Footer: Wild Hunt, 21st.dev", href: "https://21st.dev" }] },
        ]}
        colophon="The bot reaches for the bait; Hermes holds it out. Footer art from the Dolos team's reference image, toned green. Hero hands: Michelangelo, The Creation of Adam (c. 1512), public domain, via Wikimedia Commons. ΔΟΛΟΣ, the Greek spirit of trickery."
        legal="Dolos · HackUMass XIV"
        fontFamily='"Montserrat Variable", system-ui, sans-serif'
        monoFamily='"JetBrains Mono Variable", ui-monospace, monospace'
      />
    </main>
  );
}
