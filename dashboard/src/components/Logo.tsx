/** Dolos mark: one capsule split at the seam, a mirrored D (the trap copy, red) back to back with a D (the real site, blue). */
export function DolosMark({ size = 26, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className={className}>
      <path d="M15.25 9H9a7 7 0 0 0 0 14h6.25Z" fill="var(--trap)" />
      <path d="M16.75 9H23a7 7 0 0 1 0 14h-6.25Z" fill="var(--real)" />
    </svg>
  );
}

export function Wordmark({ className = "" }: { className?: string }) {
  return <span className={`font-mono font-extrabold tracking-[0.2em] ${className}`}>DOLOS</span>;
}
