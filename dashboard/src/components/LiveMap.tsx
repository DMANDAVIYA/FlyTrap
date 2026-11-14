import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { onMessage, type State } from "../feed";
import type { EventData } from "../types";
import { Panel, short } from "./Panel";

type P = [number, number];
const NODES: Record<string, P> = {
  internet: [0.06, 0.5], charon: [0.3, 0.5],
  "web-1": [0.55, 0.2], "web-2": [0.67, 0.2], "db-real": [0.61, 0.34],
  "pod-1": [0.5, 0.7], "pod-2": [0.58, 0.7], "pod-3": [0.66, 0.7], "pod-4": [0.74, 0.7], "pod-5": [0.82, 0.7],
  "backup-01": [0.92, 0.62], "model-vault": [0.92, 0.84],
};
const OLYMPUS = { x: 0.47, y: 0.07, w: 0.28, h: 0.36 };
const TARTARUS = { x: 0.44, y: 0.52, w: 0.54, h: 0.43 };
const MAX_DOTS = 200;

interface Dot { pts: P[]; t0: number; dur: number; color: string }

function css(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#fff";
}

function route(e: EventData, rr: number): { pts: P[]; color: string } {
  const start: P = [NODES.internet[0], NODES.internet[1] + ((e.id * 37) % 100) / 300 - 0.16];
  const path = e.path ?? "";
  if (e.side === "trap" || e.side === "blocked") {
    const pod = NODES[e.pod ?? "pod-1"] ?? NODES["pod-1"];
    const pts: P[] = [start, NODES.charon, pod];
    if (path.includes("internal-backup") || path.includes("/infra/backup-01")) pts.push(NODES["backup-01"]);
    if (path.includes("/infra/model-vault")) pts.push(NODES["model-vault"]);
    return { pts, color: "trap" };
  }
  return { pts: [start, NODES.charon, rr % 2 ? NODES["web-1"] : NODES["web-2"]], color: "real" };
}

function along(pts: P[], f: number): P {
  const segs = pts.length - 1;
  const x = Math.min(f * segs, segs - 1e-6);
  const i = Math.floor(x), t = x - i;
  return [pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t];
}

export function LiveMap({ s }: { s: State }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const dots = useRef<Dot[]>([]);
  const glow = useRef<Record<string, { t: number; color: string }>>({});
  const reduce = useReducedMotion();

  useEffect(() => {
    let rr = 0;
    return onMessage((m) => {
      if (m.type === "event" && (m.data.kind === "request" || m.data.kind === "beacon")) {
        const r = route(m.data, rr++);
        dots.current.push({ ...r, t0: performance.now(), dur: 900 + r.pts.length * 120 });
        if (dots.current.length > MAX_DOTS) dots.current.splice(0, dots.current.length - MAX_DOTS);
        glow.current[m.data.pod ?? (rr % 2 ? "web-1" : "web-2")] = { t: performance.now(), color: r.color };
      } else if (m.type === "event" && m.data.kind === "tripwire") {
        glow.current.charon = { t: performance.now(), color: "warn" };
      } else if (m.type === "flip") {
        glow.current[m.data.pod] = { t: performance.now(), color: "trap" };
        glow.current.charon = { t: performance.now(), color: "trap" };
      }
    });
  }, []);

  useEffect(() => {
    const c = canvas.current!;
    const ctx = c.getContext("2d")!;
    const colors = { real: css("--real"), trap: css("--trap"), warn: css("--warn"), line: css("--line"), text: css("--text-2"), ok: css("--ok") };
    let raf = 0;
    const resize = () => {
      const r = c.getBoundingClientRect();
      c.width = r.width * devicePixelRatio;
      c.height = r.height * devicePixelRatio;
    };
    const ro = new ResizeObserver(resize);
    ro.observe(c);
    resize();

    const draw = () => {
      const W = c.width, H = c.height, k = devicePixelRatio;
      const X = (p: P) => [p[0] * W, p[1] * H] as const;
      const now = performance.now();
      ctx.clearRect(0, 0, W, H);

      // zones
      const zone = (z: typeof OLYMPUS, label: string, color: string) => {
        ctx.strokeStyle = color; ctx.globalAlpha = 0.5; ctx.lineWidth = 1 * k; ctx.setLineDash([6 * k, 6 * k]);
        ctx.strokeRect(z.x * W, z.y * H, z.w * W, z.h * H); ctx.setLineDash([]); ctx.globalAlpha = 1;
        ctx.fillStyle = color; ctx.font = `600 ${12 * k}px "Chakra Petch"`; ctx.fillText(label, z.x * W + 8 * k, z.y * H + 16 * k);
      };
      zone(OLYMPUS, "OLYMPUS · real servers", colors.real);
      zone(TARTARUS, "TARTARUS · no route out", colors.trap);

      // links
      ctx.strokeStyle = colors.line; ctx.lineWidth = 1.5 * k;
      const link = (a: string, b: string) => { const [x1, y1] = X(NODES[a]); const [x2, y2] = X(NODES[b]); ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); };
      link("internet", "charon");
      ["web-1", "web-2", "pod-1", "pod-2", "pod-3", "pod-4", "pod-5"].forEach((n) => link("charon", n));
      link("web-1", "db-real"); link("web-2", "db-real"); link("pod-5", "backup-01"); link("pod-5", "model-vault");

      // dots
      dots.current = dots.current.filter((d) => now - d.t0 < d.dur);
      for (const d of dots.current) {
        const f = (now - d.t0) / d.dur;
        const [x, y] = X(along(d.pts, f));
        ctx.fillStyle = d.color === "trap" ? colors.trap : colors.real;
        ctx.globalAlpha = 0.35 + 0.65 * (1 - Math.abs(f - 0.5));
        ctx.beginPath(); ctx.arc(x, y, (d.color === "trap" ? 3.5 : 2.5) * k, 0, Math.PI * 2); ctx.fill();
      }
      ctx.globalAlpha = 1;

      // nodes
      for (const [name, p] of Object.entries(NODES)) {
        const [x, y] = X(p);
        const g = glow.current[name];
        const age = g ? (now - g.t) / 1200 : 1;
        const base = name === "internet" ? colors.text : name === "charon" ? colors.ok : name.startsWith("web") || name === "db-real" ? colors.real : colors.trap;
        const col = g && age < 1 ? (colors as Record<string, string>)[g.color] ?? base : base;
        const r = (name === "charon" ? 13 : name === "internet" ? 11 : 8) * k;
        if (g && age < 1) {
          ctx.fillStyle = col; ctx.globalAlpha = 0.25 * (1 - age);
          ctx.beginPath(); ctx.arc(x, y, r * (1.6 + age), 0, Math.PI * 2); ctx.fill(); ctx.globalAlpha = 1;
        }
        ctx.fillStyle = "#0b0f14"; ctx.strokeStyle = col; ctx.lineWidth = 2 * k;
        ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        ctx.fillStyle = colors.text; ctx.font = `${11 * k}px "IBM Plex Mono"`; ctx.textAlign = "center";
        const label = name === "charon" ? "CHARON · gateway" : name === "internet" ? "visitors" : name;
        ctx.fillText(label, x, y + r + 14 * k); ctx.textAlign = "left";
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); };
  }, []);

  const [flip, setFlip] = useState(s.lastFlip);
  useEffect(() => {
    if (!s.lastFlip) return;
    setFlip(s.lastFlip);
    const id = setTimeout(() => setFlip(null), 2400);
    return () => clearTimeout(id);
  }, [s.lastFlip]);

  return (
    <Panel title="Live map" className="col-span-8" bodyClass="relative"
      right={<span className="text-xs text-text2">{s.flips} flips · <span style={{ color: "var(--real)" }}>●</span> real <span style={{ color: "var(--trap)" }}>●</span> trapped</span>}>
      <canvas ref={canvas} className="absolute inset-0 w-full h-full" />
      <AnimatePresence>
        {flip && (
          <motion.div key={flip.at} className="absolute inset-0 flex items-center justify-center pointer-events-none"
            initial={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.4 }}>
            <div className="relative flex flex-col items-center">
              <svg width="150" height="150" viewBox="0 0 150 150" aria-hidden>
                {!reduce && (
                  <motion.circle cx="75" cy="75" r="40" fill="none" stroke="var(--trap)" strokeWidth="3"
                    initial={{ r: 40, opacity: 0.9 }} animate={{ r: 72, opacity: 0 }} transition={{ duration: 0.7, delay: 0.15 }} />
                )}
                <motion.path d="M15 75 A60 60 0 0 1 135 75" fill="none" stroke="var(--trap)" strokeWidth="7" strokeLinecap="round"
                  style={{ originX: "75px", originY: "75px" }}
                  initial={reduce ? false : { rotate: -55, y: -10 }} animate={{ rotate: 0, y: 8 }} transition={{ duration: 0.15, ease: "easeIn" }} />
                <motion.path d="M15 75 A60 60 0 0 0 135 75" fill="none" stroke="var(--trap)" strokeWidth="7" strokeLinecap="round"
                  style={{ originX: "75px", originY: "75px" }}
                  initial={reduce ? false : { rotate: 55, y: 10 }} animate={{ rotate: 0, y: -8 }} transition={{ duration: 0.15, ease: "easeIn" }} />
              </svg>
              <div className="mt-1 px-3 py-1 rounded bg-black/70 border border-trap font-display text-lg tracking-wider" style={{ color: "var(--trap)" }}>
                {flip.raider ? `${flip.raider} · ` : ""}{short(flip.session)} trapped by {flip.tripwire} → {flip.pod}
                <span className="text-text2 text-sm"> · {Number(flip.gw_ms).toFixed(2)} ms</span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Panel>
  );
}
