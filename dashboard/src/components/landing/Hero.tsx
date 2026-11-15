import { motion, useReducedMotion } from "framer-motion";
import { ArrowDown } from "lucide-react";
import { useState, type CSSProperties } from "react";
import { GlyphHand } from "./GlyphHand";
import { Vial } from "./Vial";

// Hand geometry from the assets: the bot's fingertip sits at 96% across / 64% down its image,
// Hermes' at 1% across / 50.5% down; widths 680px, heights 300px and 390px.
const BOT_TIP_X = 0.96, BOT_H = 300 / 680;
const HERMES_TIP_X = 0.013, HERMES_H = 390 / 680, LINE = 0.505 * HERMES_H;
const ease = [0.16, 1, 0.3, 1] as const;

export function Hero() {
  const still = !!useReducedMotion();
  const [reach, setReach] = useState(false);
  const enter = (from: number, delay = 0) =>
    still ? {} : { initial: { opacity: 0, x: from }, animate: { opacity: 1, x: 0 }, transition: { duration: 1.4, ease, delay } };

  const box = {
    "--wh": "clamp(250px, min(44vw, 58svh), 760px)",
    "--gap": "clamp(64px, 7vw, 116px)",
  } as CSSProperties;

  return (
    <section aria-labelledby="hero-title" className="relative isolate flex min-h-[100svh] flex-col items-center justify-center overflow-x-clip pb-12 pt-20" style={box}>
      <motion.h1
        id="hero-title"
        initial={still ? false : { opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 1.2, ease }}
        className="pointer-events-none relative z-0 select-none text-center font-display text-[min(30svh,26vw)] font-[160] uppercase leading-[0.8] tracking-[0.05em] text-text/90"
      >
        Dolos
      </motion.h1>

      {/* The reach: the bot (left, code glyphs) and Hermes (right, fresco) with the bait between them. */}
      <div className="relative z-10 -mt-[3svh] w-full sm:-mt-[9svh]" style={{ height: `calc(var(--wh) * ${HERMES_H})` }}>
        {/* Sacred geometry and the floor line, centred on the bait. */}
        <svg aria-hidden className="pointer-events-none absolute left-1/2 -translate-x-1/2 -translate-y-1/2 overflow-visible"
          style={{ top: `calc(var(--wh) * ${LINE})`, width: "min(78svh, 92vw)", height: "min(78svh, 92vw)" }} viewBox="-100 -100 200 200">
          <circle r="96" fill="none" stroke="rgb(61 255 143 / .1)" strokeWidth=".35" />
          <circle r="66" fill="none" stroke="rgb(61 255 143 / .08)" strokeWidth=".35" />
          <motion.path d="M0 -96 L83.1 48 L-83.1 48 Z" fill="none" stroke="rgb(61 255 143 / .12)" strokeWidth=".35"
            animate={still ? undefined : { rotate: 360 }} transition={{ duration: 140, repeat: Infinity, ease: "linear" }} />
        </svg>
        <div aria-hidden className="pointer-events-none absolute inset-x-0 h-px bg-gradient-to-r from-transparent via-green/25 to-transparent" style={{ top: `calc(var(--wh) * ${LINE})` }} />

        <motion.div {...enter(-80)} className="absolute top-0" style={{
          left: `calc(50% - var(--gap) / 2 - var(--wh) * ${BOT_TIP_X})`, width: "var(--wh)",
          height: `calc(var(--wh) * ${BOT_H})`, marginTop: `calc(var(--wh) * ${LINE - 0.64 * BOT_H})`,
        }}>
          <div className="h-full w-full transition-transform duration-700 ease-out" style={{ transform: reach ? "translateX(14px)" : "none" }}>
            <GlyphHand src="/hero/hand-bot.webp" bright={reach} className="h-full w-full [mask-image:linear-gradient(to_left,black_62%,transparent)]" />
          </div>
          <span className="caps absolute bottom-[-6px] left-[34%] hidden text-[10px] text-text2 sm:block">the bot</span>
        </motion.div>

        <motion.div {...enter(80, 0.1)} className="absolute top-0" style={{
          left: `calc(50% + var(--gap) / 2 - var(--wh) * ${HERMES_TIP_X})`, width: "var(--wh)", height: `calc(var(--wh) * ${HERMES_H})`,
        }}>
          <img src="/hero/hand-hermes.webp" alt="" width={680} height={390} className="h-full w-full select-none [mask-image:linear-gradient(to_right,black_60%,transparent)]" draggable={false} />
          <span className="caps absolute bottom-[8%] left-[48%] hidden text-[10px] text-text2 sm:block">Hermes</span>
        </motion.div>

        <motion.div
          className="absolute left-1/2 z-10"
          style={{ top: `calc(var(--wh) * ${LINE})`, width: "calc(var(--gap) * 0.62)", x: "-50%", y: "-50%" }}
          initial={still ? false : { opacity: 0, scale: 0.7 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.9, ease, delay: 0.7 }}
          onPointerEnter={() => setReach(true)}
          onPointerLeave={() => setReach(false)}
        >
          <motion.div animate={still ? undefined : { y: [0, -7, 0], rotate: [-14, -10, -14] }} transition={{ duration: 4.5, repeat: Infinity, ease: "easeInOut" }}
            style={{ rotate: -14 }} className="transition-[filter] duration-500" >
            <Vial glow={reach} className="h-auto w-full drop-shadow-[0_0_18px_rgba(61,255,143,.45)]" />
          </motion.div>
        </motion.div>
      </div>

      <motion.div
        initial={still ? false : { opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 1, ease, delay: 0.9 }}
        className="relative z-10 mt-6 flex flex-col items-center px-5 text-center"
      >
        <p className="max-w-[34ch] text-[clamp(1.1rem,1.7vw,1.4rem)] font-medium leading-snug">
          A honeypot for rogue AI that hides inside your real website.
        </p>
        <p className="mt-3 max-w-[58ch] text-[15px] leading-relaxed text-text2">
          The bot reaches for the bait. Hermes hands it a perfect copy of your site, full of fake data. It never finds out.
        </p>
        <a href="#how" aria-label="Scroll to how it works"
          className="mt-8 grid h-11 w-11 place-items-center rounded-full border border-line2 text-text2 transition-colors hover:border-green/60 hover:text-green">
          <motion.span className="grid place-items-center" animate={still ? undefined : { y: [0, 5, 0] }}
            transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}>
            <ArrowDown size={18} aria-hidden />
          </motion.span>
        </a>
      </motion.div>
    </section>
  );
}
