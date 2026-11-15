import { ArrowRight } from "lucide-react";
import { useEffect } from "react";
import { Hero } from "@/components/landing/Hero";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { DolosMark, Wordmark } from "@/components/Logo";
import WildHuntFooter from "@/components/ui/wild-hunt-footer";

const CREDIT = "https://commons.wikimedia.org/wiki/File:Creation_of_Adam_(Michelangelo)_Detail.jpg";
const ARBO = "https://commons.wikimedia.org/wiki/File:Peter_Nicolai_Arbo_-_The_wild_Hunt_of_Odin_-_NG.M.00258_-_National_Museum_of_Art,_Architecture_and_Design.jpg";
// the "How it works" sprites (public/how2d); the robot's CC BY-SA 4.0 asks for this credit
const KNIGHT = "https://ozanoyunbozan.itch.io/pixel-art-hooded-knight";
const ROBOT = "https://silverink.itch.io/";
const RUINS = "https://opengameart.org/content/classical-ruin-tiles";

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
          src: "/hero/footer-wild-hunt.webp",
          cutout: "/hero/footer-wild-hunt-cutout.webp",
          position: "50% 26%",
          alt: "Åsgårdsreien, the Wild Hunt of Odin: riders storming across a night sky, by Peter Nicolai Arbo, 1872, toned green",
        }}
        preset="ink"
        palette={{ background: "#030604", ink: "#3dff8f" }}
        className="dolos-footer"
        tagline="A honeypot for rogue AI · hidden inside your real website"
        sideNote="Built at HackUMass XIV · Olympus above · Tartarus below"
        columns={[
          { title: "Explore", links: [{ label: "How it works", href: "#how" }, { label: "What the bot sees", href: "#/see" }, { label: "Live console", href: "#/console" }] },
          { title: "Try it", links: [{ label: "Release the swarm", href: "#/console" }, { label: "Open the bait site", href: bait }] },
          {
            title: "Credits",
            links: [
              { label: "Hero: The Creation of Adam", href: CREDIT },
              { label: "Footer: Arbo, The Wild Hunt", href: ARBO },
              { label: "Knight: ozanoyunbozan", href: KNIGHT },
              { label: "Robot: Silver Ink, CC BY-SA 4.0", href: ROBOT },
              { label: "Ruins: surt, CC0", href: RUINS },
            ],
          },
        ]}
        colophon="Painting: Peter Nicolai Arbo, Åsgårdsreien (The Wild Hunt of Odin), 1872. National Museum, Oslo. Public domain, via Wikimedia Commons; the sky toned green, the riders in their own colours. Hero hands: Michelangelo, The Creation of Adam (c. 1512), public domain. How it works: Hooded Knight by ozanoyunbozan; Biped Robot by Silver Ink, CC BY-SA 4.0 (creativecommons.org/licenses/by-sa/4.0); Classical Ruin Tiles by surt, CC0, toned green. Footer design: Wild Hunt, 21st.dev. ΔΟΛΟΣ, the Greek spirit of trickery."
        legal="Dolos · HackUMass XIV"
        fontFamily='"Montserrat Variable", system-ui, sans-serif'
        monoFamily='"JetBrains Mono Variable", ui-monospace, monospace'
      />
    </main>
  );
}
