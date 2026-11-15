import { useReducedMotion } from "framer-motion";
import { useEffect, useRef } from "react";

const CHARS = "ΔΟΛΣΞΨΩΦΠΘ01<>/{}=#$*";
const pick = () => CHARS[Math.floor(Math.random() * CHARS.length)];

interface Cell { x: number; y: number; l: number; ch: string; ox: number; oy: number }

/**
 * The bot's hand: Michelangelo's hand rebuilt from green code glyphs, sampled from the image's
 * alpha and brightness. Glyphs fly into place once, then flicker. Pauses off screen; static with
 * reduced motion.
 */
export function GlyphHand({ src, className = "", bright = false }: { src: string; className?: string; bright?: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const boost = useRef(bright);
  const still = !!useReducedMotion();
  boost.current = bright;

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const img = new Image();
    img.src = src;
    let cells: Cell[] = [];
    let W = 0, H = 0, dpr = 1, step = 6, start = 0, raf = 0, last = 0, visible = true, alive = true;

    const build = () => {
      const r = canvas.getBoundingClientRect();
      if (!r.width || !img.complete || !img.naturalWidth) return;
      dpr = Math.min(devicePixelRatio || 1, 2);
      W = r.width; H = r.height;
      canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
      step = W < 420 ? 4 : 5;
      const cols = Math.floor(W / step), rows = Math.floor(H / step);
      const off = document.createElement("canvas");
      off.width = cols; off.height = rows;
      const o = off.getContext("2d");
      if (!o) return;
      o.drawImage(img, 0, 0, cols, rows);
      const data = o.getImageData(0, 0, cols, rows).data;
      cells = [];
      for (let y = 0; y < rows; y++) {
        for (let x = 0; x < cols; x++) {
          const i = (y * cols + x) * 4;
          if (data[i + 3] < 90) continue;
          cells.push({ x: (x + 0.5) * step, y: (y + 0.5) * step, l: data[i + 1] / 255, ch: pick(), ox: (Math.random() - 0.5) * 140, oy: (Math.random() - 0.5) * 90 });
        }
      }
    };

    const paint = (now: number) => {
      const e = still ? 1 : 1 - Math.pow(1 - Math.min(1, (now - start) / 1600), 3);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      ctx.font = `600 ${step * 1.2}px "JetBrains Mono Variable", monospace`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      const gain = boost.current ? 1.25 : 1;
      for (const c of cells) {
        if (!still && Math.random() < 0.025) c.ch = pick();
        const a = Math.min(1, (0.18 + c.l * 0.9) * gain) * e;
        ctx.fillStyle = `rgba(61,255,143,${a.toFixed(3)})`;
        ctx.fillText(c.ch, c.x + c.ox * (1 - e), c.y + c.oy * (1 - e));
      }
    };

    // ~30 fps is plenty for a flicker; stop entirely when off screen.
    const tick = (now: number) => {
      if (!alive || !visible) { raf = 0; return; }
      if (now - last > 33) { paint(now); last = now; }
      raf = requestAnimationFrame(tick);
    };
    const run = () => { if (!raf && !still) raf = requestAnimationFrame(tick); };

    img.onload = () => {
      build();
      start = performance.now();
      if (still) paint(start); else run();
    };
    const ro = new ResizeObserver(() => { build(); if (still) paint(performance.now()); });
    ro.observe(canvas);
    const io = new IntersectionObserver(([en]) => { visible = en.isIntersecting; if (visible) run(); });
    io.observe(canvas);

    return () => {
      alive = false;
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      img.onload = null;
    };
  }, [src, still]);

  return <canvas ref={ref} aria-hidden className={className} />;
}
