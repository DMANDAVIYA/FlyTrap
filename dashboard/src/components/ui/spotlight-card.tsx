// 21st.dev "spotlight-card", same props and look. Dolos changes:
//  - fast pointer tracking: one shared listener for every card, at most one update per frame, and only
//    cards the light can reach are touched. The light lives on its own overlay element, so moving it
//    restyles that small layer instead of the card's whole content (tables, charts). Before this, a
//    pointer sweep over the console spent ~12 ms per move recalculating styles;
//  - two fixed-hue presets: "dolos" (the brand green, no hue drift across the screen) and "amber" (Zeus);
//  - no `touch-action: none` (phones could not scroll over a card), no backdrop blur (nothing behind
//    the cards to blur, and it is costly), and no light on touch screens, which have no pointer to follow;
//  - typed for strict TypeScript.

import React, { useEffect, useRef, ReactNode } from 'react';

interface GlowCardProps {
  children: ReactNode;
  className?: string;
  glowColor?: 'blue' | 'purple' | 'green' | 'red' | 'orange' | 'dolos' | 'amber';
  size?: 'sm' | 'md' | 'lg';
  width?: string | number;
  height?: string | number;
  customSize?: boolean; // When true, ignores size prop and uses width/height or className
}

const glowColorMap = {
  blue: { base: 220, spread: 200 },
  purple: { base: 280, spread: 300 },
  green: { base: 120, spread: 200 },
  red: { base: 0, spread: 200 },
  orange: { base: 30, spread: 200 },
  dolos: { base: 146, spread: 0 },
  amber: { base: 40, spread: 0 }
};

const sizeMap = {
  sm: 'w-48 h-64',
  md: 'w-64 h-80',
  lg: 'w-80 h-96'
};

// ---- shared pointer tracking ---------------------------------------------------------------------
const REACH = 220; // px around a card where the 200 px spotlight can still reach its border
const lights = new Map<HTMLDivElement, boolean>(); // overlay -> lit last frame
let px = -1e4;
let py = -1e4;
let raf = 0;

function frame() {
  raf = 0;
  const w = window.innerWidth;
  const h = window.innerHeight;
  const boxes: Array<[HTMLDivElement, DOMRect]> = [];
  lights.forEach((_, el) => boxes.push([el, el.getBoundingClientRect()])); // read everything before writing
  for (const [el, r] of boxes) {
    const near = px > r.left - REACH && px < r.right + REACH && py > r.top - REACH && py < r.bottom + REACH;
    if (!near && !lights.get(el)) continue; // still dark: nothing to move
    lights.set(el, near); // one last write when the pointer leaves parks the light out of reach
    el.style.setProperty('--x', px.toFixed(2));
    el.style.setProperty('--xp', (px / w).toFixed(2));
    el.style.setProperty('--y', py.toFixed(2));
    el.style.setProperty('--yp', (py / h).toFixed(2));
  }
}
const schedule = () => {
  if (!raf) raf = requestAnimationFrame(frame);
};
const onMove = (e: PointerEvent) => {
  px = e.clientX;
  py = e.clientY;
  schedule();
};
function track(el: HTMLDivElement) {
  if (lights.size === 0) {
    document.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('scroll', schedule, { passive: true, capture: true });
  }
  lights.set(el, false);
}
function untrack(el: HTMLDivElement) {
  lights.delete(el);
  if (lights.size === 0) {
    document.removeEventListener('pointermove', onMove);
    window.removeEventListener('scroll', schedule, { capture: true });
    cancelAnimationFrame(raf);
    raf = 0;
  }
}

const beforeAfterStyles = `
  [data-glow]::before,
  [data-glow]::after {
    pointer-events: none;
    content: "";
    position: absolute;
    inset: calc(var(--border-size) * -1);
    border: var(--border-size) solid transparent;
    border-radius: calc(var(--radius) * 1px);
    background-attachment: fixed;
    background-size: calc(100% + (2 * var(--border-size))) calc(100% + (2 * var(--border-size)));
    background-repeat: no-repeat;
    background-position: 50% 50%;
    mask: linear-gradient(transparent, transparent), linear-gradient(white, white);
    mask-clip: padding-box, border-box;
    mask-composite: intersect;
  }

  [data-glow]::before {
    background-image: radial-gradient(
      calc(var(--spotlight-size) * 0.75) calc(var(--spotlight-size) * 0.75) at
      calc(var(--x, 0) * 1px)
      calc(var(--y, 0) * 1px),
      hsl(var(--hue, 210) calc(var(--saturation, 100) * 1%) calc(var(--lightness, 50) * 1%) / var(--border-spot-opacity, 1)), transparent 100%
    );
    filter: brightness(2);
  }

  [data-glow]::after {
    background-image: radial-gradient(
      calc(var(--spotlight-size) * 0.5) calc(var(--spotlight-size) * 0.5) at
      calc(var(--x, 0) * 1px)
      calc(var(--y, 0) * 1px),
      hsl(0 100% 100% / var(--border-light-opacity, 1)), transparent 100%
    );
  }

  [data-glow] [data-glow] {
    position: absolute;
    inset: 0;
    will-change: filter;
    opacity: var(--outer, 1);
    border-radius: calc(var(--radius) * 1px);
    border-width: calc(var(--border-size) * 20);
    filter: blur(calc(var(--border-size) * 10));
    background: none;
    pointer-events: none;
    border: none;
  }

  [data-glow] > [data-glow]::before {
    inset: -10px;
    border-width: 10px;
  }

  @media (hover: none) {
    [data-glow] { display: none; }
  }
`;

const GlowCard: React.FC<GlowCardProps> = ({
  children,
  className = '',
  glowColor = 'blue',
  size = 'md',
  width,
  height,
  customSize = false
}) => {
  const lightRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = lightRef.current;
    if (!el) return;
    track(el);
    return () => untrack(el);
  }, []);

  const { base, spread } = glowColorMap[glowColor];

  // Determine sizing
  const getSizeClasses = () => {
    if (customSize) {
      return ''; // Let className or inline styles handle sizing
    }
    return sizeMap[size];
  };

  // Static frame on the card; everything that follows the pointer is on the light overlay.
  const cardStyles = () => {
    const styles: Record<string, string | number> = {
      '--base': base,
      '--spread': spread,
      '--radius': '14',
      '--border': '3',
      '--backdrop': 'hsl(0 0% 60% / 0.12)',
      '--backup-border': 'var(--backdrop)',
      '--size': '200',
      '--outer': '1',
      '--border-size': 'calc(var(--border, 2) * 1px)',
      '--spotlight-size': 'calc(var(--size, 150) * 1px)',
      backgroundColor: 'var(--backdrop, transparent)',
      border: 'var(--border-size) solid var(--backup-border)',
      position: 'relative',
    };

    // Add width and height if provided
    if (width !== undefined) {
      styles.width = typeof width === 'number' ? `${width}px` : width;
    }
    if (height !== undefined) {
      styles.height = typeof height === 'number' ? `${height}px` : height;
    }

    return styles as React.CSSProperties;
  };

  const lightStyles = {
    '--x': -10000,
    '--y': -10000,
    '--hue': 'calc(var(--base) + (var(--xp, 0) * var(--spread, 0)))',
    position: 'absolute',
    inset: 0,
    borderRadius: 'inherit',
    pointerEvents: 'none',
    backgroundImage: `radial-gradient(
      var(--spotlight-size) var(--spotlight-size) at
      calc(var(--x, 0) * 1px)
      calc(var(--y, 0) * 1px),
      hsl(var(--hue, 210) calc(var(--saturation, 100) * 1%) calc(var(--lightness, 70) * 1%) / var(--bg-spot-opacity, 0.1)), transparent
    )`,
    backgroundSize: 'calc(100% + (2 * var(--border-size))) calc(100% + (2 * var(--border-size)))',
    backgroundPosition: '50% 50%',
    backgroundAttachment: 'fixed',
  } as React.CSSProperties;

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: beforeAfterStyles }} />
      <div
        style={cardStyles()}
        className={`
          ${getSizeClasses()}
          ${!customSize ? 'aspect-[3/4]' : ''}
          rounded-2xl
          relative
          grid
          grid-rows-[1fr_auto]
          shadow-[0_1rem_2rem_-1rem_black]
          p-4
          gap-4
          ${className}
        `}
      >
        <div ref={lightRef} data-glow aria-hidden style={lightStyles}>
          <div data-glow></div>
        </div>
        {children}
      </div>
    </>
  );
};

export { GlowCard }
