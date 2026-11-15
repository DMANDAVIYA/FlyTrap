/** Dolos mark: a Δ whose floor opens, with the visitor falling through the trapdoor. */
export function DolosMark({ size = 26, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className={className}>
      <path d="M13 25H4.5L16 5l11.5 20H19" fill="none" stroke="var(--green)" strokeWidth="2.4" strokeLinejoin="miter" />
      <circle cx="16" cy="28.6" r="1.9" fill="var(--green)" />
    </svg>
  );
}

export function Wordmark({ className = "" }: { className?: string }) {
  return <span className={`font-semibold tracking-[0.38em] ${className}`}>DOLOS</span>;
}
