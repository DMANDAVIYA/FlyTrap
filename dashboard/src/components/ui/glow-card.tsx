// Adapted from 21st.dev "interactive-tech-stack-bento-grid-with-hover-effects": the GlowCard shell,
// useAnimatedNumber and toSmoothPath. Dolos changes: the pointer position is written to CSS custom
// properties through a ref (no React state per mousemove, so live charts inside never re-render on
// hover), styles live in index.css (.glow-*), and the accent comes from the black-and-green tokens.

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

export const cx = (...parts: Array<string | false | null | undefined>) => parts.filter(Boolean).join(" ");

/** A card whose border, spotlight and fine grid follow the pointer. `glow` is an "r g b" token var. */
export function GlowCard({ className = "", glow, label, children }: {
  className?: string; glow?: string; label?: string; children: ReactNode;
}) {
  const ref = useRef<HTMLElement>(null);
  const move = (x: number, y: number) => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    el.style.setProperty("--x", `${x - r.left}px`);
    el.style.setProperty("--y", `${y - r.top}px`);
  };
  return (
    <section
      ref={ref}
      aria-label={label}
      onPointerMove={(e) => move(e.clientX, e.clientY)}
      className={cx("glow-card", className)}
      style={glow ? ({ "--glow": glow } as CSSProperties) : undefined}
    >
      <div aria-hidden className="glow-edge" />
      <div aria-hidden className="glow-face">
        <div className="glow-spot" />
        <div className="glow-grid" />
      </div>
      <div className="relative z-10 flex h-full min-h-0 flex-col p-5">{children}</div>
    </section>
  );
}

/** Card heading: a plain sentence-case title with an optional line under it and an item on the right. */
export function CardTitle({ children, sub, right }: { children: ReactNode; sub?: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0 flex-1 basis-40">
        <h3 className="truncate text-[19px] font-semibold leading-tight tracking-[-0.01em] text-text">{children}</h3>
        {sub && <p className="mt-1 text-[12.5px] leading-snug text-text2">{sub}</p>}
      </div>
      {right && <div className="shrink-0">{right}</div>}
    </div>
  );
}

/** Counts smoothly toward a new target; jumps straight there with reduced motion. */
export function useAnimatedNumber(target: number, duration = 700): number {
  const [value, setValue] = useState(target);
  const current = useRef(target);
  useEffect(() => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      current.current = target;
      setValue(target);
      return;
    }
    const from = current.current;
    const start = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      current.current = from + (target - from) * (1 - Math.pow(1 - t, 3));
      setValue(current.current);
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, duration]);
  return value;
}

/** Smooth line through points on a 0..100 box. */
export function toSmoothPath(points: Array<{ x: number; y: number }>): string {
  return points.reduce((d, p, i) => {
    if (i === 0) return `M ${p.x} ${p.y}`;
    const prev = points[i - 1];
    const mid = (prev.x + p.x) / 2;
    return `${d} C ${mid} ${prev.y}, ${mid} ${p.y}, ${p.x} ${p.y}`;
  }, "");
}

/** Small rounded status chip, as in the KPI footers. `good` is green, `bad` is breach red, anything else neutral. */
export function Chip({ tone = "flat", children }: { tone?: "good" | "flat" | "bad"; children: ReactNode }) {
  const cls = tone === "good" ? "bg-green/15 text-green" : tone === "bad" ? "bg-breach/15 text-breach" : "bg-text/[.07] text-text2";
  return <span className={`inline-flex shrink-0 items-center whitespace-nowrap rounded-full px-2.5 py-1 text-[11.5px] font-semibold tabular ${cls}`}>{children}</span>;
}
