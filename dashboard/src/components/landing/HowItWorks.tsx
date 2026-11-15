import { motion, useInView, useMotionValueEvent, useReducedMotion, useScroll } from "framer-motion";
import { lazy, Suspense, useEffect, useRef, useState } from "react";

// The pixel-art scene loads only when this section comes near; the SVG diagram stands in until then,
// and stays for reduced motion or when a canvas is unavailable.
const HowScene2D = lazy(() => import("./HowScene2D"));

// Plain-words version of the README's steps, plus the real-side defence. No numbers it does not state.
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
  {
    n: "06", name: "What if it reaches Olympus?",
    see: "The real site. Real pages, real login. It thinks it slipped past the trap.",
    real: "A warrior steps in: the defenders guarding the real site. Probing the real side, like walking other customers' record IDs, is a tripwire too, so the bot drops straight back into Tartarus. Hephaestus rotates every key it could have seen, and Athena can ask Zeus for a lockdown.",
  },
];

// Where the bot stands in the diagram at each step (viewBox 0 0 400 440, floor at y = 230).
const BOT = [
  { cx: 96, cy: 219 }, { cx: 150, cy: 219 }, { cx: 310, cy: 290 }, { cx: 310, cy: 290 }, { cx: 310, cy: 290 },
];
const SAGE = "rgb(176 210 190)";
const GREEN = "rgb(61 255 143)";
const BLUE = "rgb(76 141 255)"; // only the warrior, the real site's defender

// Step 6 plays as a loop: the bot slips into Olympus, the warrior rotates the keys and strikes, the bot drops back into the copy.
const ESCAPE = { duration: 5.6, times: [0, 0.2, 0.36, 0.72, 0.84, 1], repeat: Infinity, repeatDelay: 0.6, ease: "easeInOut" as const };

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

/** A hoplite in line art: crested helmet, round shield with the Dolos Δ, sword raised toward Olympus. Feet on the floor right of the temple. */
function Warrior({ strike }: { strike: boolean }) {
  return (
    <g transform="translate(402 229) scale(-1 1)" stroke={BLUE} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" fill="none"
      style={{ filter: "drop-shadow(0 0 5px rgb(76 141 255 / .55))" }}>
      {/* sword arm and sword, swinging from the hand */}
      <path d="M8 -41 L17 -47" />
      <motion.g initial={false} animate={strike ? { rotate: [0, 0, -12, -12, 62, 0] } : { rotate: 0 }}
        transition={strike ? ESCAPE : { duration: 0 }} style={{ originX: "17px", originY: "-47px" }}>
        <path d="M17 -49 L15.4 -61 L17.6 -74 L19.2 -61 Z" fill="rgb(76 141 255 / .25)" />
        <path d="M13.5 -49 H20.5" />
        <circle cx="17" cy="-45.5" r="1.3" fill={BLUE} />
      </motion.g>
      {/* crest and Corinthian helmet */}
      <path d="M-8 -63 C -4 -75 9 -76 14 -63 L 9 -61 C 6 -68 -1 -69 -4 -61 Z" fill="rgb(76 141 255 / .35)" />
      <path d="M-6 -61 C -8 -54 -8 -49 -6 -44 H 7 C 9 -50 8 -57 3 -61 Z" fill="#06101f" />
      <path d="M-5 -54 H1 M-2 -54 V-47" />
      {/* body, kilt and legs */}
      <path d="M-5 -42 H8 L6 -24 H-3 Z" fill="#06101f" />
      <path d="M-4 -24 L-5 -16 M0 -24 V-16 M3 -24 L4 -16 M6 -24 L7 -17" />
      <path d="M-2 -16 L-4 0 M4 -16 L6 0" strokeWidth="2" />
      {/* round shield with the Dolos mark */}
      <circle cx="-9" cy="-30" r="13" fill="#071a30" />
      <path d="M-11.5 -24 H-15 L-9 -36 L-3 -24 H-6.5" />
      <circle cx="-9" cy="-21" r="1.1" fill={BLUE} stroke="none" />
    </g>
  );
}

function Diagram({ step, still }: { step: number; still: boolean }) {
  const t = still ? { duration: 0 } : { type: "spring" as const, stiffness: 55, damping: 15 };
  const fade = (on: boolean) => ({ animate: { opacity: on ? 1 : 0 }, transition: still ? { duration: 0 } : { duration: 0.5 } });
  const bot = BOT[Math.min(step, 4)];
  const escape = step === 5;
  const loop = escape && !still;
  const open = step >= 2 && !escape;
  return (
    <svg viewBox="0 0 440 440" className="h-full w-full" role="img"
      aria-label={`Diagram, step ${step + 1} of ${STEPS.length}: ${STEPS[step].name}. ${STEPS[step].real}`}>
      {/* Olympus above the floor, Tartarus as its reflection below. */}
      <Temple color={SAGE} />
      <text x="310" y="98" textAnchor="middle" fill={SAGE} fontSize="11" letterSpacing="3.5" fontWeight="600" fontFamily="Montserrat Variable">OLYMPUS</text>
      <text x="310" y="112" textAnchor="middle" fill="rgb(138 162 147)" fontSize="9" fontFamily="Montserrat Variable">the real site</text>
      <motion.g {...fade(true)} initial={false} animate={{ opacity: open ? 1 : 0.35 }} transform="translate(0 460) scale(1 -1)">
        <Temple color={GREEN} />
      </motion.g>
      <motion.text x="310" y="352" textAnchor="middle" fill={GREEN} fontSize="11" letterSpacing="3.5" fontWeight="600" fontFamily="Montserrat Variable"
        initial={false} animate={{ opacity: open ? 1 : 0.45 }}>TARTARUS</motion.text>
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
        initial={false} animate={{ pathLength: [0.22, 0.48, 1, 1, 1, 1][step], opacity: escape ? 0 : 0.55 }} transition={still ? { duration: 0 } : { duration: 1.1 }} />
      <motion.path d="M18 219 H250 L300 205 L310 290" fill="none" stroke={BLUE} strokeWidth="1" strokeDasharray="3 4"
        initial={false} animate={{ pathLength: escape ? 1 : 0, opacity: escape ? 0.6 : 0 }} transition={still ? { duration: 0 } : { duration: 1.4 }} />

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

      {/* What if it reaches Olympus: the warrior defends, rotates the keys and strikes; the bot is trapped again. */}
      <motion.g initial={false} animate={loop ? { opacity: [0, 0, 1, 1, 1, 1], x: [18, 18, 0, 0, 0, 0] } : { opacity: escape ? 1 : 0, x: 0 }}
        transition={loop ? ESCAPE : { duration: still ? 0 : 0.4 }}>
        <Warrior strike={loop} />
        <text x="402" y="243" textAnchor="middle" fill={BLUE} fontSize="8" letterSpacing="1.5" fontWeight="600" fontFamily="Montserrat Variable">WARRIOR</text>
      </motion.g>
      <motion.g initial={false} animate={loop ? { opacity: [0, 0, 0, 1, 1, 0.7] } : { opacity: escape ? 1 : 0 }} transition={loop ? ESCAPE : { duration: still ? 0 : 0.4 }}>
        <motion.g animate={loop ? { rotate: [0, 0, 0, 360, 360, 360] } : { rotate: 0 }} transition={loop ? ESCAPE : { duration: 0 }} style={{ originX: "268px", originY: "62px" }}>
          <circle cx="268" cy="62" r="8" fill="none" stroke={BLUE} strokeWidth="1.2" strokeDasharray="36 14" />
        </motion.g>
        <path d="M264.5 62h6m-1 0v2.6" stroke={BLUE} strokeWidth="1.3" fill="none" />
        <text x="282" y="65.5" fill={BLUE} fontSize="9" fontFamily="JetBrains Mono Variable">keys rotated</text>
      </motion.g>
      <motion.text x="244" y="304" textAnchor="middle" fill={GREEN} fontSize="8.5" fontFamily="JetBrains Mono Variable" initial={false}
        animate={loop ? { opacity: [0, 0, 0, 0, 1, 1] } : { opacity: escape ? 1 : 0 }} transition={loop ? ESCAPE : { duration: still ? 0 : 0.4 }}>
        trapped again
      </motion.text>

      {/* The bot. */}
      <motion.circle r="7" fill={GREEN} initial={false}
        animate={loop ? { cx: [96, 250, 300, 300, 310, 310], cy: [219, 219, 205, 205, 290, 290] } : escape ? { cx: 310, cy: 290 } : bot}
        transition={loop ? ESCAPE : t} style={{ filter: "drop-shadow(0 0 6px rgb(61 255 143 / .9))" }} />
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

/** Desktop: one step of the list beside the pinned scene. Only the step in play is open; the rest are dimmed titles. */
function Chapter({ i, active }: { i: number; active: boolean }) {
  const s = STEPS[i];
  return (
    <div className={`border-l-2 py-4 pl-6 transition-[opacity,border-color] duration-300 ${active ? "border-green" : "border-line2 opacity-[.35]"}`}>
      <h3 className="flex items-baseline gap-3 font-display text-[clamp(1.6rem,2.3vw,2.1rem)] font-[300] uppercase leading-none tracking-[0.03em]">
        <span className="font-[150] text-green/70">{s.n}</span>
        {s.name}
      </h3>
      {/* Always in the DOM, so screen readers get every step. It opens as a grid row going 0fr to 1fr: framer's
          height "auto" measures, then restores the page with window.scrollTo, which cancelled smooth scrolls like Back to top. */}
      <div className={`grid transition-[grid-template-rows,opacity] duration-[350ms] ease-[cubic-bezier(.22,1,.36,1)] ${active ? "grid-rows-[1fr]" : "grid-rows-[0fr] opacity-0"}`}>
        <div className="overflow-hidden">
        <dl className="max-w-[46ch] space-y-4 pt-4">
          <div>
            <dt className="caps text-[10.5px] font-semibold text-real">They see</dt>
            <dd className="mt-1.5 text-[16px] leading-relaxed text-text/85">{s.see}</dd>
          </div>
          <div>
            <dt className="caps text-[10.5px] font-semibold text-green">What really happens</dt>
            <dd className="mt-1.5 text-[16px] leading-relaxed">{s.real}</dd>
          </div>
        </dl>
        </div>
      </div>
    </div>
  );
}

/**
 * Desktop: a tall track with a pinned panel, the step list beside the scene, the step following how far the track has
 * scrolled. Phones and reduced motion: the six steps in normal page flow, each setting the step as it comes into view.
 */
export function HowItWorks() {
  const still = !!useReducedMotion();
  const [step, setStep] = useState(0);
  const stage = useRef<HTMLDivElement>(null);
  const track = useRef<HTMLDivElement>(null);
  const near = useInView(stage, { once: true, margin: "600px 0px 600px 0px" });
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const live = ready && !failed;
  const { scrollYProgress } = useScroll({ target: track, offset: ["start start", "end end"] });
  useMotionValueEvent(scrollYProgress, "change", (v) => {
    if (still || !matchMedia("(min-width: 1024px)").matches) return; // phones step with the stacked articles
    setStep(Math.min(STEPS.length - 1, Math.floor(v * STEPS.length)));
  });
  return (
    <section id="how" aria-labelledby="how-title" className="relative mx-auto max-w-6xl scroll-mt-4 px-5 pt-24 sm:px-8">
      <h2 id="how-title" className="font-display text-[clamp(3.25rem,8vw,7rem)] font-[200] uppercase leading-[.85] tracking-[0.03em]">How it works</h2>
      <p className="mt-5 max-w-[56ch] text-lg leading-relaxed text-text2">
        One website, two worlds. Follow the bot from the front door to the trap, and see what happens if it slips past. Every step has two sides: what it sees, and what really happens.
      </p>
      <div ref={track} className={`mt-10 ${still ? "" : "lg:h-[460vh]"}`}>
      <div className={still ? "" : "lg:sticky lg:top-0 lg:flex lg:h-[100dvh] lg:items-center"}>
      <div className="grid w-full gap-x-16 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-center">
        <div ref={stage} className={`${still ? "" : "sticky top-0 z-10 lg:static"} -mx-5 h-[42svh] border-b border-line bg-bg/95 px-5 py-3 backdrop-blur-sm sm:-mx-8 sm:px-8 lg:order-2 lg:mx-0 lg:h-[78svh] lg:border-0 lg:bg-transparent lg:p-0 lg:backdrop-blur-none`}>
          <div className="relative h-full w-full">
            {/* The SVG keeps the accessible description; once the pixel scene is up it only hides. */}
            <div className={`h-full w-full transition-opacity duration-700 ${live ? "opacity-0" : ""}`}>
              <Diagram step={still ? 4 : step} still={still || live} />
            </div>
            {!still && !failed && near && (
              <Suspense fallback={null}>
                <div className={`absolute inset-0 transition-opacity duration-700 ${live ? "" : "opacity-0"}`}>
                  <HowScene2D step={step} onReady={() => setReady(true)} onFail={() => setFailed(true)} />
                </div>
              </Suspense>
            )}
          </div>
        </div>
        {!still && (
          <div className="hidden lg:order-1 lg:flex lg:flex-col lg:gap-1">
            {STEPS.map((_, i) => <Chapter key={i} i={i} active={i === step} />)}
          </div>
        )}
        <div className={still ? "lg:order-1" : "lg:hidden"}>
          {STEPS.map((_, i) => <Step key={i} i={i} onActive={setStep} />)}
        </div>
      </div>
      </div>
      </div>
    </section>
  );
}
