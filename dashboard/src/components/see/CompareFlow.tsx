import { useReducedMotion } from "framer-motion";
import {
  ArrowDownToLine, Bot, Check, ChevronsLeftRight, DoorOpen, Eye, FileKey2, Fingerprint, Globe, KeyRound, LogIn, Pause, Play, Zap,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

// Plain-words version of the README's five steps. No numbers it does not state.
export const STEPS: {
  name: string; see: string; real: string;
  seeNode: { t: string; i: LucideIcon }; realNode: { t: string; s: string; i: LucideIcon };
}[] = [
  {
    name: "The front door",
    see: "A normal website. Pages load, the login works.",
    real: "Every request passes Charon, our gateway. It decides with simple rules in memory, so there is no AI in the way and no visible delay.",
    seeNode: { t: "Homepage", i: Globe }, realNode: { t: "Charon", s: "the gateway", i: DoorOpen },
  },
  {
    name: "The bait",
    see: "A leaked password file, a hidden admin link, an old backup nobody cleaned up.",
    real: "Tripwires. Real customers never see them. Only scripts and AI agents snooping around find them.",
    seeNode: { t: "Juicy files", i: FileKey2 }, realNode: { t: "Tripwire", s: "bait touched", i: Zap },
  },
  {
    name: "The switch",
    see: "Nothing changes. Same pages, same login, plenty of data to steal.",
    real: "The floor opens. The bot now lives in Tartarus: its own copy of the site, same code, fake data, no route back to the real servers.",
    seeNode: { t: "Logged in", i: LogIn }, realNode: { t: "Trapdoor", s: "into Tartarus", i: ArrowDownToLine },
  },
  {
    name: "The loot",
    see: "API keys and tokens, ready to use.",
    real: "Every key is unique to one visitor. The moment one is used, it names who took it and links everyone who shares it.",
    seeNode: { t: "API keys", i: KeyRound }, realNode: { t: "Marked key", s: "names the thief", i: Fingerprint },
  },
  {
    name: "The watchers",
    see: "Maybe a slow page or two.",
    real: "Sixteen defending AI agents label the visitor, slow it down and write the incident report. Big moves wait for Zeus: a human.",
    seeNode: { t: "All good", i: Check }, realNode: { t: "Watchers", s: "16 agents and Zeus", i: Eye },
  },
];

type P = [number, number];
interface Layout {
  w: number; h: number; node: number; start: P; see: P[]; real: P[];
  floor: [number, number, number, number]; band: [number, number, number, number]; top: P; under: P;
}
// Same geometry under both views, so the bar compares one place in two worlds.
const WIDE: Layout = {
  w: 1000, h: 430, node: 150, start: [64, 120],
  see: [[225, 120], [390, 120], [555, 120], [720, 120], [885, 120]],
  real: [[225, 120], [390, 120], [555, 222], [720, 330], [885, 330]],
  floor: [0, 222, 1000, 222], band: [0, 222, 1000, 208], top: [170, 54], under: [26, 404],
};
const TALL: Layout = {
  w: 400, h: 740, node: 138, start: [110, 96],
  see: [[110, 170], [110, 290], [110, 410], [110, 530], [110, 650]],
  real: [[110, 170], [110, 290], [200, 410], [292, 530], [292, 650]],
  floor: [200, 0, 200, 740], band: [200, 0, 200, 740], top: [16, 724], under: [214, 724],
};

const MOVE = 1100, DWELL = 1700, LAST = 2600;
// Time at which the bot arrives at node k (1..5) inside one loop.
const arriveAt = (k: number) => k * MOVE + (k - 1) * DWELL;
const LOOP = 5 * MOVE + 4 * DWELL + LAST;
const ease = (f: number) => 1 - Math.pow(1 - f, 3);
const pct = (v: number, of: number) => `${(v / of) * 100}%`;
const line = (pts: P[]) => pts.map((p, i) => `${i ? "L" : "M"}${p[0]} ${p[1]}`).join(" ");

function Node({ L, at, active, icon: Icon, title, sub, n, kind }: {
  L: Layout; at: P; active: boolean; icon: LucideIcon; title: string; sub?: string; n: number; kind: "see" | "real";
}) {
  const real = kind === "real";
  return (
    <div
      className={`absolute flex -translate-x-1/2 -translate-y-1/2 items-center gap-2.5 rounded-xl border px-2.5 py-2 transition-[border-color,box-shadow,background-color] duration-500 ${
        real
          ? active ? "border-green bg-[#06200f] shadow-[0_0_24px_rgba(61,255,143,.35)]" : "border-green/35 bg-[#04120a]"
          : active ? "border-real bg-[#121c16] shadow-[0_0_20px_rgba(176,210,190,.18)]" : "border-real/25 bg-[#0c140f]"
      }`}
      style={{ left: pct(at[0], L.w), top: pct(at[1], L.h), width: pct(L.node, L.w) }}
    >
      <Icon size={16} strokeWidth={1.7} className={`shrink-0 ${real ? "text-green" : "text-real"}`} aria-hidden />
      <div className="min-w-0 leading-tight">
        <div className="font-mono text-[9.5px] text-text2">0{n}</div>
        <div className={`text-[12px] font-semibold ${real ? "text-green" : "text-text"}`}>{title}</div>
        {sub && <div className="text-[10px] text-text2">{sub}</div>}
      </div>
    </div>
  );
}

function Layer({ L, kind, step, token }: { L: Layout; kind: "see" | "real"; step: number; token: (el: SVGCircleElement | null) => void }) {
  const real = kind === "real";
  const pts = [L.start, ...(real ? L.real : L.see)];
  const color = real ? "rgb(61 255 143)" : "rgb(176 210 190)";
  return (
    <div className={`absolute inset-0 ${real ? "bg-[#020503]" : "bg-[#0a110d]"}`}>
      <svg viewBox={`0 0 ${L.w} ${L.h}`} className="absolute inset-0 h-full w-full" aria-hidden>
        {real ? (
          <>
            <rect x={L.band[0]} y={L.band[1]} width={L.band[2]} height={L.band[3]} fill="rgb(61 255 143 / .05)" />
            <line x1={L.floor[0]} y1={L.floor[1]} x2={L.floor[2]} y2={L.floor[3]} stroke="rgb(228 240 232 / .35)" strokeDasharray="2 6" />
            <text x={L.top[0]} y={L.top[1]} fill="rgb(176 210 190)" fontSize="11" letterSpacing="3" fontWeight="600" fontFamily="Montserrat Variable">{L.w > 500 ? "OLYMPUS · THE REAL SITE" : "OLYMPUS"}</text>
            <text x={L.under[0]} y={L.under[1]} fill="rgb(61 255 143)" fontSize="11" letterSpacing="3" fontWeight="600" fontFamily="Montserrat Variable">{L.w > 500 ? "TARTARUS · THE COPY" : "TARTARUS"}</text>
          </>
        ) : (
          <>
            <text x={L.top[0]} y={L.top[1]} fill="rgb(176 210 190)" fontSize="11" letterSpacing="3" fontWeight="600" fontFamily="Montserrat Variable">THE WEBSITE</text>
            <text x={L.w > 500 ? 500 : 300} y={L.w > 500 ? 300 : 410} textAnchor="middle" fill="rgb(138 162 147)" fontSize="13" fontStyle="italic" fontFamily="Montserrat Variable">Everything looks normal.</text>
          </>
        )}
        <path d={line(pts)} fill="none" stroke={color} strokeOpacity=".22" strokeWidth="2" />
        <path d={line(pts)} fill="none" stroke={color} strokeWidth="2" className="flow-dash" />
        <circle ref={token} cx={L.start[0]} cy={L.start[1]} r={L.w > 500 ? 8 : 9} fill={color}
          style={{ filter: `drop-shadow(0 0 ${real ? 8 : 4}px ${color})` }} />
      </svg>
      <div className="absolute flex -translate-x-1/2 -translate-y-1/2 items-center gap-1.5 rounded-full border border-line2 bg-bg px-2.5 py-1 text-[11px] text-text2"
        style={{ left: pct(L.start[0], L.w), top: pct(L.start[1] - (L.w > 500 ? 44 : 40), L.h) }}>
        <Bot size={13} aria-hidden /> the bot
      </div>
      {STEPS.map((s, i) => (
        <Node key={i} L={L} kind={kind} n={i + 1} active={step === i + 1}
          at={(real ? L.real : L.see)[i]} icon={real ? s.realNode.i : s.seeNode.i}
          title={real ? s.realNode.t : s.seeNode.t} sub={real ? s.realNode.s : undefined} />
      ))}
    </div>
  );
}

/** A live before/after window: drag the bar left for what really happens, right for what the bot sees. */
export function CompareFlow() {
  const still = !!useReducedMotion();
  const box = useRef<HTMLDivElement>(null);
  const grip = useRef<HTMLDivElement>(null);
  const pos = useRef(50);
  const dragging = useRef(false);
  const tokens = useRef<{ see: SVGCircleElement | null; real: SVGCircleElement | null }>({ see: null, real: null });
  const [wide, setWide] = useState(() => typeof window === "undefined" || matchMedia("(min-width: 640px)").matches);
  const [step, setStep] = useState(still ? 1 : 0);
  const [playing, setPlaying] = useState(!still);
  const clock = useRef({ t0: 0, from: 0 });
  const L = wide ? WIDE : TALL;

  const setPos = useCallback((p: number) => {
    pos.current = Math.min(100, Math.max(0, p));
    box.current?.style.setProperty("--pos", String(pos.current));
    grip.current?.setAttribute("aria-valuenow", String(Math.round(pos.current)));
    grip.current?.setAttribute("aria-valuetext", `${Math.round(100 - pos.current)}% shows what really happens`);
  }, []);

  // Pick the layout from the window's own width.
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWide(e.contentRect.width >= 600));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Place both bots for a time inside the loop; report the step they stand on.
  const place = useCallback((t: number) => {
    let acc = 0;
    for (let k = 0; k < 5; k++) {
      const end = acc + MOVE;
      if (t < end) {
        const f = ease((t - acc) / MOVE);
        for (const kind of ["see", "real"] as const) {
          const pts = [L.start, ...(kind === "real" ? L.real : L.see)];
          const a = pts[k], b = pts[k + 1];
          tokens.current[kind]?.setAttribute("cx", String(a[0] + (b[0] - a[0]) * f));
          tokens.current[kind]?.setAttribute("cy", String(a[1] + (b[1] - a[1]) * f));
        }
        return k;
      }
      acc = end + (k === 4 ? LAST : DWELL);
      if (t < acc) {
        for (const kind of ["see", "real"] as const) {
          const p = (kind === "real" ? L.real : L.see)[k];
          tokens.current[kind]?.setAttribute("cx", String(p[0]));
          tokens.current[kind]?.setAttribute("cy", String(p[1]));
        }
        return k + 1;
      }
    }
    return 5;
  }, [L]);

  // The live loop: runs only while playing and on screen.
  useEffect(() => {
    if (!playing) return;
    let raf = 0, visible = true, last = -1;
    clock.current.t0 = performance.now() - clock.current.from;
    const tick = (now: number) => {
      if (!visible) { raf = 0; return; }
      const t = (now - clock.current.t0) % LOOP;
      clock.current.from = t;
      const s = place(t);
      if (s !== last) { last = s; setStep(s); }
      raf = requestAnimationFrame(tick);
    };
    const io = new IntersectionObserver(([e]) => {
      visible = e.isIntersecting;
      if (visible && !raf) { clock.current.t0 = performance.now() - clock.current.from; raf = requestAnimationFrame(tick); }
    });
    if (box.current) io.observe(box.current);
    raf = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(raf); io.disconnect(); };
  }, [playing, place]);

  // Paused: keep the bots on the chosen step, also after a layout change.
  useEffect(() => {
    if (!playing) place(step ? arriveAt(step) : 0);
  }, [playing, step, place]);

  // One gentle sweep the first time the window is seen, so the bar reads as draggable.
  useEffect(() => {
    const el = box.current;
    if (!el || still) return;
    let raf = 0;
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      io.disconnect();
      const t0 = performance.now();
      const sweep = (now: number) => {
        const f = Math.min(1, (now - t0) / 2200);
        if (dragging.current) return;
        setPos(50 - Math.sin(f * Math.PI * 2) * 16 * (1 - f));
        if (f < 1) raf = requestAnimationFrame(sweep);
      };
      raf = requestAnimationFrame(sweep);
    }, { threshold: 0.6 });
    io.observe(el);
    return () => { io.disconnect(); cancelAnimationFrame(raf); };
  }, [still, setPos]);

  const fromPointer = (e: PointerEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    setPos(((e.clientX - r.left) / r.width) * 100);
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const d = { ArrowLeft: -5, ArrowDown: -5, ArrowRight: 5, ArrowUp: 5, PageDown: -20, PageUp: 20 }[e.key];
    if (d !== undefined) setPos(pos.current + d);
    else if (e.key === "Home") setPos(0);
    else if (e.key === "End") setPos(100);
    else return;
    e.preventDefault();
  };
  const goTo = (k: number) => {
    setPlaying(false);
    clock.current.from = arriveAt(k);
    setStep(k);
  };

  const shown = STEPS[Math.max(1, step) - 1];
  return (
    <div>
      <div className="overflow-hidden rounded-2xl border border-line2/80 bg-panel">
        <div className="flex items-center gap-3 border-b border-line px-4 py-2.5">
          <span className={`h-2 w-2 rounded-full bg-green ${playing ? "dolos-pulse" : ""}`} />
          <span className="caps text-[10px] font-semibold text-text2">Live flow</span>
          <span className="font-mono text-[11px] text-text2">step {Math.max(1, step)} / 5</span>
          <button onClick={() => (playing ? setPlaying(false) : setPlaying(true))}
            className="ml-auto flex items-center gap-1.5 rounded-full border border-line2 px-3 py-1 text-[11px] text-text2 hover:text-text"
            aria-label={playing ? "Pause the flow" : "Play the flow"}>
            {playing ? <Pause size={12} aria-hidden /> : <Play size={12} aria-hidden />} {playing ? "Pause" : "Play"}
          </button>
        </div>

        <div
          ref={box}
          className="relative w-full select-none [touch-action:pan-y]"
          style={{ aspectRatio: `${L.w} / ${L.h}`, ["--pos" as string]: 50 }}
          onPointerDown={(e) => { dragging.current = true; e.currentTarget.setPointerCapture(e.pointerId); fromPointer(e); }}
          onPointerMove={(e) => { if (dragging.current) fromPointer(e); }}
          onPointerUp={() => { dragging.current = false; }}
          onPointerCancel={() => { dragging.current = false; }}
        >
          <div aria-hidden className="absolute inset-0">
            <Layer L={L} kind="see" step={step} token={(el) => { tokens.current.see = el; }} />
            <div className="absolute inset-0" style={{ clipPath: "inset(0 0 0 calc(var(--pos) * 1%))" }}>
              <Layer L={L} kind="real" step={step} token={(el) => { tokens.current.real = el; }} />
            </div>
            <span className="caps absolute left-3 top-3 rounded-full bg-bg/80 px-2.5 py-1 text-[9.5px] font-semibold text-real"
              style={{ opacity: "clamp(0, calc((var(--pos) - 10) / 12), 1)" }}><span className="sm:hidden">They see</span><span className="hidden sm:inline">What they see</span></span>
            <span className="caps absolute right-3 top-3 rounded-full bg-bg/80 px-2.5 py-1 text-[9.5px] font-semibold text-green"
              style={{ opacity: "clamp(0, calc((90 - var(--pos)) / 12), 1)" }}><span className="sm:hidden">Really</span><span className="hidden sm:inline">What really happens</span></span>
          </div>

          {/* The bar. */}
          <div className="pointer-events-none absolute inset-y-0 w-0.5 -translate-x-1/2 bg-green shadow-[0_0_14px_rgba(61,255,143,.7)]"
            style={{ left: "calc(var(--pos) * 1%)" }} />
          <div
            ref={grip}
            role="slider"
            tabIndex={0}
            aria-label="Compare views: drag left for what really happens, right for what the bot sees"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={50}
            aria-valuetext="50% shows what really happens"
            onKeyDown={onKey}
            className="absolute top-1/2 flex h-11 w-11 -translate-x-1/2 -translate-y-1/2 cursor-ew-resize items-center justify-center rounded-full border border-green bg-[#04140b] text-green shadow-[0_0_20px_rgba(61,255,143,.45)]"
            style={{ left: "calc(var(--pos) * 1%)" }}
          >
            <ChevronsLeftRight size={18} aria-hidden />
          </div>
        </div>
      </div>

      <div role="group" aria-label="Steps" className="mt-4 grid grid-cols-5 gap-2">
        {STEPS.map((s, i) => (
          <button key={s.name} onClick={() => goTo(i + 1)} aria-pressed={step === i + 1}
            className={`rounded-xl border px-2 py-2.5 text-left transition-colors ${step === i + 1 ? "border-green/70 bg-green/10" : "border-line2/70 hover:border-text2/60"}`}>
            <span className="block text-center font-mono text-[12px] text-text2 sm:text-left sm:text-[10px]">0{i + 1}</span>
            <span className={`hidden text-[12.5px] font-semibold leading-tight sm:block ${step === i + 1 ? "text-green" : "text-text"}`}>{s.name}</span>
          </button>
        ))}
      </div>

      <h2 className="mt-6 font-display text-[clamp(2rem,4vw,3rem)] font-[300] uppercase leading-none tracking-[0.03em]">
        <span className="text-green/70">0{Math.max(1, step)}</span> {shown.name}
      </h2>
      <div className="mt-4 grid gap-5 md:grid-cols-2" aria-live="polite">
        <div>
          <div className="caps text-[10.5px] font-semibold text-real">They see</div>
          <p className="mt-1.5 text-[17px] leading-relaxed text-text/85">{shown.see}</p>
        </div>
        <div className="md:border-l md:border-line md:pl-6">
          <div className="caps text-[10.5px] font-semibold text-green">What really happens</div>
          <p className="mt-1.5 text-[17px] leading-relaxed">{shown.real}</p>
        </div>
      </div>
    </div>
  );
}
