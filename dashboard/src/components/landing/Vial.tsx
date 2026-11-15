/** The bait: a small glass vial of `.env`, glowing green. Pure SVG, sized by its parent. */
export function Vial({ className = "", glow = false }: { className?: string; glow?: boolean }) {
  return (
    <svg viewBox="0 0 80 140" className={className} aria-hidden>
      <defs>
        <radialGradient id="vial-halo" cx="50%" cy="58%" r="50%">
          <stop offset="0%" stopColor="#3dff8f" stopOpacity={glow ? 0.55 : 0.32} />
          <stop offset="100%" stopColor="#3dff8f" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="vial-liquid" x1="0" x2="1">
          <stop offset="0%" stopColor="#1fb862" />
          <stop offset="45%" stopColor="#5dffa6" />
          <stop offset="100%" stopColor="#139a4e" />
        </linearGradient>
        <linearGradient id="vial-cap" x1="0" x2="1">
          <stop offset="0%" stopColor="#6f8a7a" />
          <stop offset="50%" stopColor="#dbe9df" />
          <stop offset="100%" stopColor="#56705f" />
        </linearGradient>
      </defs>
      <circle cx="40" cy="82" r="40" fill="url(#vial-halo)" />
      {/* cap and crimp */}
      <rect x="25" y="8" width="30" height="16" rx="4" fill="url(#vial-cap)" />
      <rect x="28" y="23" width="24" height="8" rx="2" fill="#9db3a5" />
      {/* glass */}
      <path d="M30 31h20v8c8 3 12 8 12 16v62c0 7-5 12-12 12H30c-7 0-12-5-12-12V55c0-8 4-13 12-16Z" fill="rgba(200,255,225,.08)" stroke="rgba(220,255,235,.55)" strokeWidth="1.5" />
      {/* liquid */}
      <path d="M20.5 70h39v47c0 5.5-4 9.5-9.5 9.5h-20c-5.5 0-9.5-4-9.5-9.5Z" fill="url(#vial-liquid)" opacity={glow ? 1 : 0.9} />
      {/* label */}
      <rect x="19" y="78" width="42" height="26" rx="2" fill="#e8f3ec" />
      <text x="40" y="96" textAnchor="middle" fontFamily="JetBrains Mono Variable, monospace" fontWeight="800" fontSize="14" fill="#04140b">.env</text>
      {/* glass highlight */}
      <path d="M25 50v62" stroke="rgba(255,255,255,.55)" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}
