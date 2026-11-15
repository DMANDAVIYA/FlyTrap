// The bait: a pixel-art vial of `.env`, glowing green, on a 16 x 25 grid (one cell = 5 units). Sized by its parent.
// o glass edge, h highlight, g glass, L/l/d liquid light/mid/dark, b label (".env" is written on it as text), c/C cork, s rim
const ROWS = [
  "......cCCc......",
  ".....cCCCCc.....",
  ".....cccccc.....",
  ".....ssssss.....",
  "......ohgo......",
  "......ohgo......",
  "......ohgo......",
  ".....ohhggo.....",
  "....ohgggggo....",
  "...ohgggggggo...",
  "..ohgggggggggo..",
  "..ohgggggggggo..",
  "..ohLLLLLLLLLo..",
  "..ohlllllllldo..",
  "..ohbbbbbbbbbo..",
  "..ohbbbbbbbbbo..",
  "..ohbbbbbbbbbo..",
  "..ohlllllllldo..",
  "..ohlLlllllldo..",
  "..ohlllllllldo..",
  "..ohllllllLldo..",
  "..ohlllllllldo..",
  "..oglllllllldo..",
  "...oddddddddo...",
  "....oooooooo....",
];
const PAL: Record<string, string> = {
  o: "#9fc4af", h: "#deeed6", g: "#16301f", L: "#7dffb6", l: "#2fd27a", d: "#13924b",
  b: "#deeed6", c: "#9a6a3c", C: "#c08a52", s: "#b0d2be",
};
// one rect per run of same-colour cells in a row
const RUNS = ROWS.flatMap((row, y) => {
  const out: { ch: string; x: number; y: number; n: number }[] = [];
  for (let x = 0; x < row.length; ) {
    let n = 1;
    while (row[x + n] === row[x]) n++;
    if (PAL[row[x]]) out.push({ ch: row[x], x, y, n });
    x += n;
  }
  return out;
});

export function Vial({ className = "", glow = false }: { className?: string; glow?: boolean }) {
  return (
    <svg viewBox="0 0 80 140" className={className} aria-hidden>
      <defs>
        <radialGradient id="vial-halo" cx="50%" cy="58%" r="50%">
          <stop offset="0%" stopColor="#3dff8f" stopOpacity={glow ? 0.55 : 0.32} />
          <stop offset="100%" stopColor="#3dff8f" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="40" cy="82" r="40" fill="url(#vial-halo)" />
      <g shapeRendering="crispEdges">
        {RUNS.map((r) => (
          <rect key={`${r.x}-${r.y}`} x={r.x * 5} y={r.y * 5 + 8} width={r.n * 5} height={5}
            fill={glow && r.ch === "l" ? "#5dffa6" : PAL[r.ch]} />
        ))}
      </g>
      {/* the label: rows 14-16, x 20-65 */}
      <text x="42.5" y="89" textAnchor="middle" fontFamily="JetBrains Mono Variable, monospace" fontWeight="800" fontSize="12" fill="#0b1f13">.env</text>
    </svg>
  );
}
