// The card every console panel sits in, plus useAnimatedNumber and toSmoothPath (adapted from 21st.dev
// "interactive-tech-stack-bento-grid-with-hover-effects"). The shell is the 21st.dev spotlight card
// (spotlight-card.tsx): a border light that follows the pointer, brand green, amber for Zeus.

import { useEffect, useRef, useState, type ReactNode } from "react";
import { GlowCard as Spotlight } from "./spotlight-card";

export const cx = (...parts: Array<string | false | null | undefined>) => parts.filter(Boolean).join(" ");

/** A console card. `glow` names a token var; "var(--warn-rgb)" turns the light amber for Zeus. */
export function GlowCard({ className = "", glow, label, children }: {
  className?: string; glow?: string; label?: string; children: ReactNode;
}) {
  return (
    <Spotlight customSize glowColor={glow?.includes("warn") ? "amber" : "dolos"} className={cx("min-h-0 !gap-0 !p-0", className)}>
      <section aria-label={label} className="glow-card relative z-10 flex h-full min-h-0 min-w-0 flex-col p-5">{children}</section>
    </Spotlight>
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
