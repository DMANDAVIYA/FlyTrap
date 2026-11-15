import { motion, useInView, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

// Plain-words version of the README's five steps. No numbers it does not state.
const STEPS = [
  {
    n: "01", name: "The front door",
    see: "A normal website. Pages load, the login works.",
    real: "Every request passes Charon, our gateway. It decides with simple rules in memory, so there is no AI in the way and no visible delay.",
  },
  {
    n: "02", name: "The bait",
    see: "A leaked password file, a hidden admin link, an old backup nobody cleaned up.",
    real: "Tripwires. Real customers never see them. Only scripts and AI agents snooping around find them.",
  },
  {
    n: "03", name: "The switch",
    see: "Nothing changes. Same pages, same login, plenty of data to steal.",
    real: "The floor opens. They now live in Tartarus: their own copy of the site, same code, fake data, no route back to the real servers.",
  },
  {
    n: "04", name: "The loot",
    see: "API keys and tokens, ready to use.",
    real: "Every key is unique to one visitor. The moment one is used, it names who took it and links everyone who shares it.",
  },
  {
    n: "05", name: "The watchers",
    see: "Maybe a slow page or two.",
    real: "Sixteen defending AI agents label each visitor as human, scanner or AI agent, slow it down and write the incident report. Big moves wait for Zeus: a human.",
  },
];

// Where the bot stands in the diagram at each step (viewBox 0 0 400 440, floor at y = 230).
const BOT = [
  { cx: 96, cy: 219 }, { cx: 150, cy: 219 }, { cx: 310, cy: 290 }, { cx: 310, cy: 290 }, { cx: 310, cy: 290 },
];
const SAGE = "rgb(176 210 190)";
const GREEN = "rgb(61 255 143)";

function Temple({ color, opacity = 1 }: { color: string; opacity?: number }) {
  return (
    <g fill="none" stroke={color} strokeWidth="1.6" opacity={opacity}>
      <path d="M248 164 L310 126 L372 164 Z" />
      <path d="M252 164 H368 V172 H252 Z" />
      {[264, 289, 314, 339].map((x) => <path key={x} d={`M${x} 172 V220 M${x + 12} 172 V220`} />)}
      <path d="M248 220 H372 V229 H248 Z" />
    </g>
  );
}

function Diagram({ step, still }: { step: number; still: boolean }) {
  const t = still ? { duration: 0 } : { type: "spring" as const, stiffness: 55, damping: 15 };
  const fade = (on: boolean) => ({ animate: { opacity: on ? 1 : 0 }, transition: still ? { duration: 0 } : { duration: 0.5 } });
  const bot = BOT[step];
  const open = step >= 2;
  return (
    <svg viewBox="0 0 400 440" className="h-full w-full" role="img"
      aria-label={`Diagram, step ${step + 1} of 5: ${STEPS[step].name}. ${STEPS[step].real}`}>
      {/* Olympus above the floor, Tartarus as its reflection below. */}
      <Temple color={SAGE} />
      <text x="310" y="98" textAnchor="middle" fill={SAGE} fontSize="11" letterSpacing="3.5" fontWeight="600" fontFamily="Montserrat Variable">OLYMPUS</text>
      <text x="310" y="112" textAnchor="middle" fill="rgb(138 162 147)" fontSize="9" fontFamily="Montserrat Variable">the real site</text>
      <motion.g {...fade(true)} animate={{ opacity: open ? 1 : 0.35 }} transform="translate(0 460) scale(1 -1)">
        <Temple color={GREEN} />
      </motion.g>
      <motion.text x="310" y="352" textAnchor="middle" fill={GREEN} fontSize="11" letterSpacing="3.5" fontWeight="600" fontFamily="Montserrat Variable"
        animate={{ opacity: open ? 1 : 0.45 }}>TARTARUS</motion.text>
      <text x="310" y="368" textAnchor="middle" fill="rgb(138 162 147)" fontSize="9" fontFamily="Montserrat Variable">the copy · fake data</text>

      {/* The floor, with Charon's gate and the trapdoor. */}
      <path d="M16 230 H140 M190 230 H384" stroke="rgb(228 240 232 / .45)" strokeWidth="1.4" />
      <path d="M58 230 V172 a18 18 0 0 1 36 0 V230" fill="none" stroke={SAGE} strokeWidth="1.6" />
      <text x="76" y="252" textAnchor="middle" fill="rgb(138 162 147)" fontSize="9" letterSpacing="2.5" fontFamily="Montserrat Variable">CHARON</text>
      <motion.line x1="140" y1="230" x2="165" y2="230" stroke={GREEN} strokeWidth="2" style={{ originX: "140px", originY: "230px" }}
        animate={{ rotate: open ? 72 : 0 }} transition={t} />
      <motion.line x1="190" y1="230" x2="165" y2="230" stroke={GREEN} strokeWidth="2" style={{ originX: "190px", originY: "230px" }}
        animate={{ rotate: open ? -72 : 0 }} transition={t} />

      {/* The bait on the trapdoor. */}
      <motion.g {...fade(step >= 1 && step < 3)} initial={false}>
        <rect x="158" y="196" width="14" height="5" rx="1.5" fill="rgb(219 233 223)" />
        <rect x="157" y="201" width="16" height="26" rx="4" fill="rgb(61 255 143 / .2)" stroke={GREEN} strokeWidth="1.2" />
        <rect x="157.5" y="212" width="15" height="7" fill="rgb(232 243 236)" />
        <text x="165" y="218" textAnchor="middle" fontSize="5.5" fontWeight="800" fill="#04140b" fontFamily="JetBrains Mono Variable">.env</text>
      </motion.g>

      {/* The path the bot took. */}
      <motion.path d="M18 219 H150 L165 260 L310 290" fill="none" stroke={GREEN} strokeWidth="1" strokeDasharray="3 4"
        initial={false} animate={{ pathLength: [0.22, 0.48, 1, 1, 1][step], opacity: 0.55 }} transition={still ? { duration: 0 } : { duration: 1.1 }} />

      {/* Marked loot. */}
      <motion.g {...fade(step === 3)} initial={false}>
        <path d="M318 282 L344 262" stroke={GREEN} strokeWidth="1" strokeDasharray="2 3" />
        <rect x="344" y="248" width="46" height="18" rx="9" fill="rgb(61 255 143 / .14)" stroke={GREEN} strokeWidth="1" />
        <text x="367" y="260.5" textAnchor="middle" fill={GREEN} fontSize="8" fontFamily="JetBrains Mono Variable">key #7f3a</text>
      </motion.g>

      {/* The watchers. */}
      {[22, 38].map((r, i) => (
        <motion.circle key={r} cx={BOT[4].cx} cy={BOT[4].cy} r={r} fill="none" stroke={GREEN} strokeWidth="1"
          initial={false} animate={step === 4 ? (still ? { opacity: 0.6 } : { opacity: [0.7, 0.15, 0.7], scale: [1, 1.12, 1] }) : { opacity: 0 }}
          transition={still ? { duration: 0 } : { duration: 2.4, repeat: step === 4 ? Infinity : 0, delay: i * 0.4 }}
          style={{ originX: `${BOT[4].cx}px`, originY: `${BOT[4].cy}px` }} />
      ))}

      {/* The bot. */}
      <motion.circle r="7" fill={GREEN} initial={false} animate={bot} transition={t} style={{ filter: "drop-shadow(0 0 6px rgb(61 255 143 / .9))" }} />
    </svg>
  );
}

function Step({ i, onActive }: { i: number; onActive: (i: number) => void }) {
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref, { amount: 0.6 });
  useEffect(() => { if (inView) onActive(i); }, [inView, i, onActive]);
  const s = STEPS[i];
  return (
    <article ref={ref} className="flex min-h-[64svh] flex-col justify-start pb-10 pt-[8svh] lg:min-h-[78svh]">
      <span className="font-display text-[clamp(3.5rem,7vw,6rem)] font-[150] leading-none text-green/70">{s.n}</span>
      <h3 className="mt-2 font-display text-[clamp(2.4rem,4.6vw,4rem)] font-[300] uppercase leading-[.9] tracking-[0.03em]">{s.name}</h3>
      <dl className="mt-6 max-w-[46ch] space-y-5">
        <div>
          <dt className="caps text-[10.5px] font-semibold text-real">They see</dt>
          <dd className="mt-1.5 text-[17px] leading-relaxed text-text/85">{s.see}</dd>
        </div>
        <div>
          <dt className="caps text-[10.5px] font-semibold text-green">What really happens</dt>
          <dd className="mt-1.5 text-[17px] leading-relaxed">{s.real}</dd>
        </div>
      </dl>
    </article>
  );
}

/** Five steps in normal page flow; the pinned diagram follows the bot as each step comes into view. */
export function HowItWorks() {
  const still = !!useReducedMotion();
  const [step, setStep] = useState(0);
  return (
    <section id="how" aria-labelledby="how-title" className="relative mx-auto max-w-6xl scroll-mt-4 px-5 pt-24 sm:px-8">
      <h2 id="how-title" className="font-display text-[clamp(3.25rem,8vw,7rem)] font-[200] uppercase leading-[.85] tracking-[0.03em]">How it works</h2>
      <p className="mt-5 max-w-[56ch] text-lg leading-relaxed text-text2">
        One website, two worlds. Follow the bot from the front door to the trap. Every step has two sides: what it sees, and what really happens.
      </p>
      <div className="mt-10 grid gap-x-16 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className={`${still ? "" : "sticky top-0 z-10"} -mx-5 h-[42svh] border-b border-line bg-bg/95 px-5 py-3 backdrop-blur-sm sm:-mx-8 sm:px-8 lg:order-2 lg:top-[11svh] lg:mx-0 lg:h-[78svh] lg:border-0 lg:bg-transparent lg:p-0 lg:backdrop-blur-none`}>
          <Diagram step={still ? 4 : step} still={still} />
        </div>
        <div className="lg:order-1">
          {STEPS.map((_, i) => <Step key={i} i={i} onActive={setStep} />)}
        </div>
      </div>
    </section>
  );
}
