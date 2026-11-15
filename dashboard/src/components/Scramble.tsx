import { useReducedMotion } from "framer-motion";
import { useEffect, useRef } from "react";
import { TextScramble } from "@/components/ui/modern-animated-hero-section";

/**
 * Text that decodes like the hero title. Visible by default; with `onView` it decodes once when
 * it scrolls into view, otherwise on every change of `text`. Screen readers get the plain text.
 */
export function Scramble({ text, className = "", onView = false }: { text: string; className?: string; onView?: boolean }) {
  const ref = useRef<HTMLSpanElement>(null);
  const fx = useRef<TextScramble | null>(null);
  const first = useRef(true);
  const still = useReducedMotion();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const initial = first.current;
    first.current = false;
    if (still) {
      el.textContent = text;
      return;
    }
    fx.current ??= new TextScramble(el);
    if (!onView) {
      if (!initial) fx.current.setText(text);
      return () => fx.current?.cancel();
    }
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      fx.current?.setText(text);
      io.disconnect();
    }, { threshold: 0.6 });
    io.observe(el);
    return () => {
      io.disconnect();
      fx.current?.cancel();
    };
  }, [text, onView, still]);

  return (
    <span className={className}>
      <span className="sr-only">{text}</span>
      <span ref={ref} aria-hidden>{text}</span>
    </span>
  );
}
