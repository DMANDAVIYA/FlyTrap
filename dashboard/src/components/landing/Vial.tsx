/** The bait: a glass bottle of `.env`, glowing green (public/hero/vial.webp). Sized by its parent; brighter while the bot reaches for it. */
export function Vial({ className = "", glow = false }: { className?: string; glow?: boolean }) {
  return (
    <img
      src="/hero/vial.webp"
      alt=""
      aria-hidden
      width={240}
      height={563}
      draggable={false}
      className={`select-none transition-[filter] duration-500 ${glow ? "brightness-125" : ""} ${className}`}
    />
  );
}
