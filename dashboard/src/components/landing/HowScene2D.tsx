import { KeyRound } from "lucide-react";
import { useEffect, useRef } from "react";

/*
 * The "How it works" diagram as a pixel-art scene on a canvas: same six steps, same scroll (`step`).
 * Sprites live in /public/how2d, each with a provenance sidecar:
 *   knight-*.png  "Hooded Knight Boss" by ozanoyunbozan (commercial use allowed, no resale)
 *   robot.png     "Biped Robot" by Silver Ink, CC BY-SA 4.0 (credited on the page)
 *   ruins.png     "Classical Ruin Tiles" by surt, CC0: temple, gate, vial and chest are cut from it here
 * The world is 256 x 368 pixels drawn at one scale and blown up by whole multiples, so pixels stay square.
 * The knight's frames are shrunk to a third on load, so it stands as tall as the robot.
 * The set is toned toward the black-and-green world in the browser; the knight and the robot keep their colours.
 */

const W = 256;
const H = 368;
const FLOOR = 184; // top of the floor band; Olympus stands on it
const UNDER = 190; // underside of the floor band; Tartarus hangs from it, upside down
const TRAP = { x: 72, w: 24 }; // the trapdoor in the floor
const TEMPLE_X = 108;
const GATE_X = 4; // Charon's gate: two columns under one arch
const KNIGHT_X = 180; // where the warrior stands in step 6: at the temple door
const FADE = 20; // the sky, floor and glow fade out over this many pixels at each side
const ESCAPE_S = 8.4; // step 6 loop length, seconds
// step 6 beats, in seconds into the loop: the attack clip starts at 4.2 and its blade is out from frame 8 (HIT);
// the robot hangs in the copy from LAND
const HIT = 4.2 + 8 / 12;
const LAND = HIT + 1.4;
// the robot's hop at the warrior: from x0 to x1, feet h px up, so the third-size blade (15-16 px above the floor,
// reaching x 136-157 from KNIGHT_X) crosses its middle
const LEAP = { x0: 130, x1: 142, h: 4 };
const TRAP_MID = TRAP.x + TRAP.w / 2;

type Rect = [number, number, number, number];
const TILE: Record<string, Rect> = {
  pediment: [488, 32, 144, 40],
  column: [264, 192, 16, 64],
  ledge: [264, 0, 16, 16],
  arch: [488, 0, 32, 32], // left half of one bay of an arcade, cornice to keystone; drawn twice, the second mirrored
  vial: [489, 72, 14, 16],
  chest: [488, 105, 32, 23],
  chestOpen: [520, 105, 32, 23],
};

// focus of each step, in world pixels: [x, y, w, h]
const FOCUS: Rect[] = [
  [0, 70, 132, 140],
  [24, 104, 128, 112],
  [0, 40, 256, 296],
  [96, 176, 160, 150],
  [92, 172, 164, 162],
  [0, 28, 256, 316],
];

type Clip = { img: CanvasImageSource; fw: number; fh: number; n: number; fps: number; fx: number; fy: number; row?: number };
type Pos = { x: number; y: number };
type Act =
  | { k: "walk"; to: Pos; speed: number }
  | { k: "fall"; to: Pos; t: number }
  | { k: "warp"; to: Pos; down: boolean; face: 1 | -1 }
  | { k: "rest"; face: 1 | -1 };
type LabelKey = "olympus" | "tartarus" | "charon" | "env" | "loot" | "warrior" | "rotated" | "trapped";

const load = (src: string) =>
  new Promise<HTMLImageElement>((ok, fail) => {
    const im = new Image();
    im.onload = () => ok(im);
    im.onerror = fail;
    im.src = src;
  });
const damp = (a: number, b: number, k: number, dt: number) => a + (b - a) * (1 - Math.exp(-k * dt));
const ease = (u: number) => u * u * (3 - 2 * u);
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/** Draws frame `f` of a clip with its feet on (x, y). flipX faces it left; flipY hangs it upside down. */
function frame(g: CanvasRenderingContext2D, c: Clip, f: number, x: number, y: number, flipX = false, flipY = false) {
  const i = ((f % c.n) + c.n) % c.n;
  g.save();
  g.translate(Math.round(x), Math.round(y));
  g.scale(flipX ? -1 : 1, flipY ? -1 : 1);
  g.drawImage(c.img, i * c.fw, (c.row ?? 0) * c.fh, c.fw, c.fh, -c.fx, -c.fy, c.fw, c.fh);
  g.restore();
}
const tile = (g: CanvasRenderingContext2D, img: HTMLImageElement, r: Rect, x: number, y: number) =>
  g.drawImage(img, r[0], r[1], r[2], r[3], Math.round(x), Math.round(y), r[2], r[3]);

/**
 * Shrinks a one-row pixel-art sheet by a whole factor k, frame by frame (fw need not divide by k): each k x k block
 * becomes the mean of its solid pixels, or stays clear when under 4/9 solid.
 */
function shrink(img: HTMLImageElement, fw: number, fh: number, k: number) {
  const src = document.createElement("canvas");
  src.width = img.width;
  src.height = img.height;
  const sg = src.getContext("2d")!;
  sg.drawImage(img, 0, 0);
  const a = sg.getImageData(0, 0, src.width, src.height).data;
  const n = Math.round(img.width / fw);
  const cw = Math.ceil(fw / k);
  const ch = Math.ceil(fh / k);
  const c = document.createElement("canvas");
  c.width = cw * n;
  c.height = ch;
  const cg = c.getContext("2d")!;
  const im = cg.createImageData(c.width, c.height);
  for (let f = 0; f < n; f++) {
    for (let y = 0; y < ch; y++) {
      for (let x = 0; x < cw; x++) {
        let cells = 0;
        let m = 0;
        let r = 0;
        let gr = 0;
        let b = 0;
        for (let j = y * k; j < Math.min(fh, y * k + k); j++) {
          for (let i = x * k; i < Math.min(fw, x * k + k); i++) {
            cells++;
            const p = (j * src.width + f * fw + i) * 4;
            if (a[p + 3] < 128) continue;
            m++;
            r += a[p];
            gr += a[p + 1];
            b += a[p + 2];
          }
        }
        if (m * 9 < cells * 4) continue;
        im.data.set([r / m, gr / m, b / m, 255], (y * c.width + f * cw + x) * 4);
      }
    }
  }
  cg.putImageData(im, 0, 0);
  return c;
}

// a bird on its upstroke and downstroke, 7 x 4 ("#" is a pixel); the watchers circle as sixteen of these
const BIRD = [
  ["#.....#", ".#...#.", "..#.#..", "...#..."],
  [".......", "...#...", ".##.##.", "#.....#"],
];
const bird = (g: CanvasRenderingContext2D, x: number, y: number, pose: number) =>
  BIRD[pose].forEach((row, j) => [...row].forEach((p, i) => p === "#" && g.fillRect(x - 3 + i, y - 2 + j, 1, 1)));

const STEP_H = 9; // each of the temple's three steps
const TEMPLE_H = 40 + 16 + 64 + 3 * STEP_H; // pediment, ledge, columns, steps

/** Olympus: steps, five columns, the entablature and the pediment, on its own canvas (feet of the steps on its bottom row). */
function buildTemple(ruins: HTMLImageElement) {
  const c = document.createElement("canvas");
  c.width = 144;
  c.height = TEMPLE_H;
  const g = c.getContext("2d")!;
  g.imageSmoothingEnabled = false;
  // three steps in the tiles' own palette: sandstone body, light top edge, dark foot line
  [144, 136, 128].forEach((w, i) => {
    const y = TEMPLE_H - STEP_H * (i + 1);
    const x = (144 - w) / 2;
    g.fillStyle = "#d2aa99";
    g.fillRect(x, y, w, STEP_H);
    g.fillStyle = "#deeed6";
    g.fillRect(x, y, w, 1);
    g.fillStyle = "#757161";
    g.fillRect(x, y + STEP_H - 1, w, 1);
  });
  // 28 px apart, so all five bases stand on the top step (x 8-136)
  for (let i = 0; i < 5; i++) tile(g, ruins, TILE.column, 8 + i * 28, 56);
  for (let x = 0; x < 144; x += 16) tile(g, ruins, TILE.ledge, x, 40);
  tile(g, ruins, TILE.pediment, 0, 0);
  return c;
}

export default function HowScene2D({ step, onReady, onFail }: { step: number; onReady: () => void; onFail: () => void }) {
  const host = useRef<HTMLDivElement>(null);
  const labels = useRef<Partial<Record<LabelKey, HTMLDivElement | null>>>({});
  const stepRef = useRef(step);
  const setStepRef = useRef<((s: number) => void) | null>(null);

  useEffect(() => {
    stepRef.current = step;
    setStepRef.current?.(step);
  }, [step]);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const view = document.createElement("canvas");
    view.setAttribute("aria-hidden", "true");
    view.style.cssText = "display:block;width:100%;height:100%;image-rendering:pixelated";
    el.prepend(view);
    const out = view.getContext("2d");
    if (!out) {
      onFail();
      return;
    }
    let disposed = false;
    let raf = 0;
    let visible = true;
    let ro: ResizeObserver | null = null;
    let io: IntersectionObserver | null = null;

    Promise.all(["ruins", "robot", "knight-idle", "knight-run", "knight-attack", "knight-power"].map((n) => load(`/how2d/${n}.png`)))
      .then(([ruins, robotImg, kIdle, kRun, kAttack, kPower]) => {
        if (disposed) return;
        const robot = {
          right: { img: robotImg, fw: 32, fh: 32, n: 6, fps: 10, fx: 13, fy: 27, row: 1 } as Clip,
          left: { img: robotImg, fw: 32, fh: 32, n: 6, fps: 10, fx: 18, fy: 27, row: 3 } as Clip,
          hurt: { img: robotImg, fw: 32, fh: 32, n: 2, fps: 6, fx: 13, fy: 27, row: 4 } as Clip,
        };
        // frames at a third of the source size; the feet anchors were measured on the shrunk frames
        const knight = {
          idle: { img: shrink(kIdle, 100, 100, 3), fw: 34, fh: 34, n: 8, fps: 8, fx: 11, fy: 29 } as Clip,
          run: { img: shrink(kRun, 100, 100, 3), fw: 34, fh: 34, n: 10, fps: 12, fx: 11, fy: 32 } as Clip,
          attack: { img: shrink(kAttack, 180, 100, 3), fw: 60, fh: 34, n: 17, fps: 12, fx: 10, fy: 29 } as Clip,
          power: { img: shrink(kPower, 100, 180, 3), fw: 34, fh: 60, n: 19, fps: 12, fx: 10, fy: 55 } as Clip,
        };

        // ---- the set, drawn once ----------------------------------------------------------------
        const temple = buildTemple(ruins);
        const set = document.createElement("canvas");
        set.width = W;
        set.height = H;
        const s = set.getContext("2d")!;
        s.imageSmoothingEnabled = false;
        // night above, a green glow far below
        const sky = s.createLinearGradient(0, 0, 0, FLOOR);
        sky.addColorStop(0, "#030604");
        sky.addColorStop(1, "#0a140e");
        s.fillStyle = sky;
        s.fillRect(0, 0, W, FLOOR);
        const deep = s.createLinearGradient(0, UNDER, 0, H);
        deep.addColorStop(0, "#04120a");
        deep.addColorStop(1, "#030604");
        s.fillStyle = deep;
        s.fillRect(0, UNDER, W, H - UNDER);
        let seed = 7;
        const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
        for (let i = 0; i < 34; i++) {
          s.fillStyle = i % 5 ? "rgba(222,238,214,.35)" : "rgba(222,238,214,.8)";
          s.fillRect(Math.floor(rnd() * W), Math.floor(rnd() * 120), 1, 1);
        }
        // the floor band, with a gap for the trapdoor
        const band = (x0: number, x1: number) => {
          s.fillStyle = "#2a2f2b";
          s.fillRect(x0, FLOOR, x1 - x0, UNDER - FLOOR);
          s.fillStyle = "#6f7a72";
          s.fillRect(x0, FLOOR, x1 - x0, 1);
          s.fillStyle = "#16301f";
          s.fillRect(x0, UNDER - 1, x1 - x0, 1);
        };
        band(0, TRAP.x);
        band(TRAP.x + TRAP.w, W);
        // the backdrop so far fades out toward both sides; the stone drawn next stays crisp
        const side = s.createLinearGradient(0, 0, W, 0);
        side.addColorStop(0, "rgba(0,0,0,0)");
        side.addColorStop(FADE / W, "#000");
        side.addColorStop(1 - FADE / W, "#000");
        side.addColorStop(1, "rgba(0,0,0,0)");
        s.globalCompositeOperation = "destination-in";
        s.fillStyle = side;
        s.fillRect(0, 0, W, H);
        s.globalCompositeOperation = "source-over";
        // the stone, toned toward sage marble; the copy below in green line light
        s.filter = "saturate(.35) sepia(.2) hue-rotate(62deg) brightness(.82)";
        s.drawImage(temple, TEMPLE_X, FLOOR - TEMPLE_H);
        // Charon's gate: columns under the arch's piers (both shafts 12 px, 48 px apart), the arch's half drawn twice
        tile(s, ruins, TILE.column, GATE_X, FLOOR - 64);
        tile(s, ruins, TILE.column, GATE_X + 48, FLOOR - 64);
        tile(s, ruins, TILE.arch, GATE_X, FLOOR - 96);
        s.save();
        s.translate(GATE_X + 64, FLOOR - 96);
        s.scale(-1, 1);
        tile(s, ruins, TILE.arch, 0, 0);
        s.restore();
        s.filter = "none";
        const copy = document.createElement("canvas");
        copy.width = temple.width;
        copy.height = temple.height;
        const cg = copy.getContext("2d")!;
        cg.drawImage(temple, 0, 0);
        cg.globalCompositeOperation = "source-atop";
        cg.fillStyle = "rgba(61,255,143,.62)";
        cg.fillRect(0, 0, copy.width, copy.height);
        s.save();
        s.globalAlpha = 0.55;
        s.translate(TEMPLE_X, UNDER);
        s.scale(1, -1);
        s.drawImage(copy, 0, -TEMPLE_H);
        s.restore();

        const world = document.createElement("canvas");
        world.width = W;
        world.height = H;
        const g = world.getContext("2d")!;
        g.imageSmoothingEnabled = false;

        // ---- direction ----------------------------------------------------------------------------
        const bot = { x: -20, y: FLOOR, down: false, face: 1 as 1 | -1, moving: false, hurt: false, queue: [] as Act[] };
        let current = 0;
        let clock = 0;
        let escapeStart = 0;
        let trap = 0; // 0 closed .. 1 open
        let vialY = 0;
        const cam = { x: W / 2, y: H / 2, z: 2 };
        const want = { x: W / 2, y: H / 2, z: 2 };

        const plan = (st: number): Act[] => {
          const A: Act[] = [];
          const up = !bot.down;
          if (st === 0) {
            if (!up || bot.x > 40) A.push({ k: "warp", to: { x: -20, y: FLOOR }, down: false, face: 1 });
            A.push({ k: "walk", to: { x: 40, y: FLOOR }, speed: 34 }, { k: "rest", face: 1 });
          } else if (st === 1) {
            if (!up) A.push({ k: "warp", to: { x: 40, y: FLOOR }, down: false, face: 1 });
            A.push({ k: "walk", to: { x: 80, y: FLOOR }, speed: 34 }, { k: "rest", face: 1 });
          } else if (st === 2) {
            if (up) A.push({ k: "walk", to: { x: 82, y: FLOOR }, speed: 40 }, { k: "fall", to: { x: 84, y: UNDER }, t: 0 });
            A.push({ k: "walk", to: { x: 150, y: UNDER }, speed: 40 }, { k: "rest", face: 1 });
          } else {
            if (up) A.push({ k: "warp", to: { x: 150, y: UNDER }, down: true, face: 1 });
            else A.push({ k: "walk", to: { x: 150, y: UNDER }, speed: 44 });
            A.push({ k: "rest", face: 1 });
          }
          return A;
        };

        const setStep = (st: number) => {
          current = st;
          if (st === 5) escapeStart = clock;
          else bot.queue = plan(st);
        };

        const runQueue = (dt: number) => {
          const a = bot.queue[0];
          bot.moving = false;
          bot.hurt = false;
          if (!a) return;
          if (a.k === "warp") {
            Object.assign(bot, { x: a.to.x, y: a.to.y, down: a.down, face: a.face });
            bot.queue.shift();
          } else if (a.k === "walk") {
            const d = a.to.x - bot.x;
            bot.y = a.to.y;
            if (Math.abs(d) < 0.5) {
              bot.x = a.to.x;
              bot.queue.shift();
              return;
            }
            bot.face = d > 0 ? 1 : -1;
            bot.moving = true;
            bot.x += Math.sign(d) * Math.min(Math.abs(d), a.speed * dt);
          } else if (a.k === "fall") {
            a.t += dt;
            if (a.t > 0.5) {
              const u = clamp((a.t - 0.5) / 0.7, 0, 1);
              bot.x = a.to.x;
              bot.y = FLOOR + (H - FLOOR - 80) * Math.sin(Math.PI * u) * 0.4 + (a.to.y - FLOOR) * u;
              bot.down = u > 0.5;
            }
            if (a.t > 1.2) {
              bot.y = a.to.y;
              bot.down = true;
              bot.queue.shift();
            }
          } else {
            bot.face = a.face;
          }
        };

        // step 6 on one clock: the robot runs at the real temple and waits while the warrior powers up (the keys rotate),
        // leaps at it, meets the blade at the top of the jump, is thrown back onto the trapdoor and drops into the copy
        const escape = (t: number) => {
          const toss = HIT + 0.6; // lands on the open trapdoor
          if (t < 2.6) {
            Object.assign(bot, { x: -20 + (LEAP.x0 + 20) * ease(t / 2.6), y: FLOOR, down: false, face: 1, moving: true, hurt: false });
          } else if (t < 4.4) {
            Object.assign(bot, { x: LEAP.x0, y: FLOOR, down: false, face: 1, moving: false, hurt: false });
          } else if (t < HIT) {
            const u = (t - 4.4) / (HIT - 4.4); // rising, slowing to the top
            Object.assign(bot, { x: LEAP.x0 + (LEAP.x1 - LEAP.x0) * u, y: FLOOR - LEAP.h * (1 - (1 - u) ** 2), down: false, face: 1, moving: false, hurt: false });
          } else if (t < toss) {
            const u = (t - HIT) / (toss - HIT); // thrown back: up a few px, then down onto the trapdoor
            Object.assign(bot, { x: LEAP.x1 + (TRAP_MID - LEAP.x1) * u, y: FLOOR - (LEAP.h + 39 * u - (LEAP.h + 39) * u * u), down: false, face: 1, moving: false, hurt: true });
          } else if (t < LAND) {
            const u = (t - toss) / (LAND - toss); // the step 3 drop: through the gap, flipping at the bottom, up onto the copy's floor
            Object.assign(bot, { x: TRAP_MID, y: FLOOR + 41.6 * Math.sin(Math.PI * u) + (UNDER - FLOOR) * u, down: u > 0.5, face: 1, moving: false, hurt: true });
          } else {
            Object.assign(bot, { x: TRAP_MID, y: UNDER, down: true, face: 1, moving: false, hurt: t < LAND + 0.6 });
          }
          // the warrior runs in from the right, powers up and strikes; its clip and frame come from the same t
          kx = KNIGHT_X;
          let clip = knight.idle;
          let f = Math.floor(t * knight.idle.fps);
          if (t < 0.8) return; // not on stage yet
          if (t < 2.2) {
            clip = knight.run;
            f = Math.floor(t * knight.run.fps);
            kx = W + 16 + (KNIGHT_X - W - 16) * ((t - 0.8) / 1.4);
          } else if (t >= 2.6 && t < 2.6 + knight.power.n / knight.power.fps) {
            clip = knight.power;
            f = Math.floor((t - 2.6) * knight.power.fps);
          } else if (t >= 4.2 && t < 4.2 + knight.attack.n / knight.attack.fps) {
            clip = knight.attack;
            f = Math.floor((t - 4.2) * knight.attack.fps);
          }
          frame(g, clip, f, kx, FLOOR, true);
        };
        let kx = KNIGHT_X; // the warrior's x, for its label

        // the watchers: sixteen birds circling the robot in step 5, the near half in front of it
        const ring = (front: boolean) => {
          g.fillStyle = "#deeed6";
          for (let i = 0; i < 16; i++) {
            const a = clock * 0.9 + (i / 16) * Math.PI * 2;
            if (Math.sin(a) > 0 !== front) continue;
            bird(g, Math.round(bot.x + Math.cos(a) * 34), Math.round(bot.y + 16 + Math.sin(a) * 14), Math.floor(clock * 6 + i * 0.7) % 2);
          }
        };

        const sizeView = () => {
          const dpr = Math.min(devicePixelRatio || 1, 3);
          const w = Math.max(1, Math.round(el.clientWidth * dpr));
          const h = Math.max(1, Math.round(el.clientHeight * dpr));
          if (view.width !== w || view.height !== h) {
            view.width = w;
            view.height = h;
          }
          return dpr;
        };
        ro = new ResizeObserver(sizeView);
        ro.observe(el);
        sizeView();

        const aim = (st: number) => {
          const [fx, fy, fw, fh] = FOCUS[st];
          const dpr = Math.min(devicePixelRatio || 1, 3);
          // whole multiples only, never below one CSS pixel per world pixel
          want.z = Math.max(Math.round(dpr), Math.floor(Math.min(view.width / fw, view.height / fh)));
          const vw = view.width / want.z;
          const vh = view.height / want.z;
          want.x = vw >= W ? W / 2 : clamp(fx + fw / 2, vw / 2, W - vw / 2);
          want.y = vh >= H ? H / 2 : clamp(fy + fh / 2, vh / 2, H - vh / 2);
        };

        const anchors: Record<LabelKey, () => Pos> = {
          olympus: () => ({ x: TEMPLE_X + 72, y: FLOOR - TEMPLE_H - 10 }),
          tartarus: () => ({ x: TEMPLE_X + 72, y: UNDER + TEMPLE_H + 14 }),
          charon: () => ({ x: 34, y: UNDER + 9 }),
          env: () => ({ x: TRAP.x + 18, y: FLOOR - 24 + vialY }),
          loot: () => ({ x: 196, y: UNDER + 40 }),
          warrior: () => ({ x: kx, y: FLOOR - 36 }),
          rotated: () => ({ x: 64, y: FLOOR - 118 }),
          trapped: () => ({ x: TRAP_MID, y: UNDER + 40 }),
        };
        const op: Record<LabelKey, number> = { olympus: 0, tartarus: 0, charon: 0, env: 0, loot: 0, warrior: 0, rotated: 0, trapped: 0 };

        let last = performance.now();
        const draw = (now: number) => {
          raf = 0;
          if (disposed || !visible) return;
          const dt = Math.min(0.05, (now - last) / 1000);
          last = now;
          clock += dt;
          const st = current;
          const escT = st === 5 ? (clock - escapeStart) % ESCAPE_S : 0;

          g.clearRect(0, 0, W, H);
          g.drawImage(set, 0, 0);

          // trapdoor: two leaves hinged at the edges of the gap, swinging down
          const open = (st >= 2 && st <= 4) || (st === 5 && escT > HIT && escT < LAND + 0.6);
          trap = damp(trap, open ? 1 : 0, 6, dt);
          const reach = Math.round(12 * trap);
          g.fillStyle = "#854c30";
          if (reach < 2) {
            g.fillRect(TRAP.x, FLOOR + 1, TRAP.w, 4);
            g.fillStyle = "#442434";
            g.fillRect(TRAP.x + 11, FLOOR + 1, 2, 4);
          } else {
            for (let i = 0; i < 12; i++) {
              const dx = Math.round(i * (1 - trap)), dy = Math.round(i * trap);
              g.fillRect(TRAP.x + dx, FLOOR + 1 + dy, 2, 3);
              g.fillRect(TRAP.x + TRAP.w - 2 - dx, FLOOR + 1 + dy, 2, 3);
            }
          }

          // the bait on the trapdoor, falling with the robot in step 3
          const vialOn = st === 1 || st === 2;
          vialY = st === 2 && trap > 0.5 ? Math.min(vialY + 140 * dt, 120) : st === 1 ? 0 : vialY;
          if (vialOn && vialY < 110) {
            const bob = st === 1 ? Math.round(Math.sin(clock * 3)) : 0;
            g.save();
            g.filter = "hue-rotate(-90deg) saturate(1.4)";
            tile(g, ruins, TILE.vial, TRAP.x + 11, FLOOR - 16 + bob + vialY);
            g.restore();
          }

          // the loot: a chest in the copy, opened in step 4
          if (st === 3 || st === 4) {
            g.save();
            g.translate(180, UNDER);
            g.scale(1, -1);
            g.filter = "saturate(.6) hue-rotate(40deg)";
            const [cx, cy, cw, ch] = st === 3 ? TILE.chestOpen : TILE.chest;
            g.drawImage(ruins, cx, cy, cw, ch, 0, -ch, cw, ch); // hangs from the underside, upside down
            g.restore();
            if (st === 3) {
              g.fillStyle = "#3dff8f";
              for (let i = 0; i < 6; i++) {
                const a = clock * 2 + i;
                g.fillRect(196 + Math.round(Math.cos(a) * 12), UNDER + 30 + Math.round(Math.sin(a * 1.3) * 8), 1, 1);
              }
            }
          }

          if (st === 4) ring(false);

          if (st === 5) escape(escT);
          else runQueue(dt);

          // the robot (in step 6 the knight was drawn inside escape(), behind it)
          const clip = bot.hurt ? robot.hurt : bot.face > 0 ? robot.right : robot.left;
          const f = bot.moving || bot.hurt ? Math.floor(clock * clip.fps) : 0;
          frame(g, clip, f, bot.x, bot.y, false, bot.down);
          if (st === 4) ring(true);
          // the hit: a burst of light where the blade meets the robot
          if (st === 5 && escT >= HIT && escT < HIT + 0.3) {
            const k = (escT - HIT) / 0.3;
            const r = 3 + Math.round(k * 7);
            const hx = LEAP.x1;
            const hy = FLOOR - LEAP.h - 12;
            g.fillStyle = `rgba(222,238,214,${(1 - k).toFixed(2)})`;
            for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [1, -1], [-1, 1], [-1, -1]]) {
              g.fillRect(hx + dx * r, hy + dy * r, 1, 1);
              g.fillRect(hx + dx * (r + 1), hy + dy * (r + 1), 1, 1);
            }
          }

          // camera: damped toward the step's framing, whole multiples once settled
          aim(st);
          cam.x = damp(cam.x, want.x, 3, dt);
          cam.y = damp(cam.y, want.y, 3, dt);
          cam.z = Math.abs(cam.z - want.z) < 0.03 ? want.z : damp(cam.z, want.z, 4, dt);
          out.imageSmoothingEnabled = false;
          out.clearRect(0, 0, view.width, view.height);
          const z = cam.z;
          const ox = Math.round(view.width / 2 - cam.x * z);
          const oy = Math.round(view.height / 2 - cam.y * z);
          out.drawImage(world, ox, oy, W * z, H * z);
          // where the view cuts through the world, that side fades out too
          const edge = FADE * z;
          out.globalCompositeOperation = "destination-out";
          for (const [cut, x0, x1] of [[-ox, 0, edge], [ox + W * z - view.width, view.width, view.width - edge]]) {
            if (cut <= 0) continue;
            const fade = out.createLinearGradient(x0, 0, x1, 0);
            fade.addColorStop(0, `rgba(0,0,0,${Math.min(1, cut / edge).toFixed(3)})`);
            fade.addColorStop(1, "rgba(0,0,0,0)");
            out.fillStyle = fade;
            out.fillRect(Math.min(x0, x1), 0, edge, view.height);
          }
          out.globalCompositeOperation = "source-over";

          // labels follow their anchors, in CSS pixels
          const dpr = view.width / Math.max(1, el.clientWidth);
          const shown: Record<LabelKey, number> = {
            olympus: 1,
            tartarus: st >= 2 && st <= 4 ? 1 : 0.6,
            charon: st <= 1 || (st === 5 && escT < HIT) ? 1 : 0, // gone before the robot lands under it
            env: st === 1 ? 1 : 0,
            loot: st === 3 ? 1 : 0,
            warrior: st === 5 && escT > 1.2 ? 1 : 0,
            rotated: st === 5 && escT > 3.2 ? 1 : 0,
            trapped: st === 5 && escT > LAND ? 1 : 0,
          };
          for (const k of Object.keys(anchors) as LabelKey[]) {
            const node = labels.current[k];
            if (!node) continue;
            op[k] = damp(op[k], shown[k], 7, dt);
            const p = anchors[k]();
            const sx = (ox + p.x * z) / dpr;
            const sy = (oy + p.y * z) / dpr;
            const inside = sx > 30 && sx < el.clientWidth - 30 && sy > 8 && sy < el.clientHeight - 8;
            node.style.opacity = inside && op[k] > 0.01 ? op[k].toFixed(3) : "0";
            node.style.transform = `translate(-50%, -50%) translate(${sx.toFixed(1)}px, ${sy.toFixed(1)}px)`;
          }
          raf = requestAnimationFrame(draw);
        };

        io = new IntersectionObserver(([e]) => {
          visible = e.isIntersecting;
          if (visible && !raf) {
            last = performance.now();
            raf = requestAnimationFrame(draw);
          }
        });
        io.observe(el);

        setStep(stepRef.current);
        aim(current);
        Object.assign(cam, want);
        setStepRef.current = setStep;
        raf = requestAnimationFrame(draw);
        requestAnimationFrame(() => !disposed && onReady());
      })
      .catch(() => !disposed && onFail());

    return () => {
      disposed = true;
      setStepRef.current = null;
      if (raf) cancelAnimationFrame(raf);
      ro?.disconnect();
      io?.disconnect();
      view.remove();
    };
    // mount once: onReady/onFail are the parent's state setters, and step changes go through setStepRef
  }, []);

  const mark = (k: LabelKey) => (n: HTMLDivElement | null) => {
    labels.current[k] = n;
  };
  const base = "pointer-events-none absolute left-0 top-0 select-none whitespace-nowrap text-center opacity-0 will-change-transform";
  return (
    <div ref={host} aria-hidden className="absolute inset-0 overflow-hidden">
      <div ref={mark("olympus")} className={base}>
        <div className="caps text-[11px] font-semibold text-real">Olympus</div>
        <div className="mt-1 text-[11px] text-text2">the real site</div>
      </div>
      <div ref={mark("tartarus")} className={base}>
        <div className="caps text-[11px] font-semibold text-green">Tartarus</div>
        <div className="mt-1 text-[11px] text-text2">the copy · fake data</div>
      </div>
      <div ref={mark("charon")} className={`${base} caps rounded-full bg-bg/80 px-2.5 py-1 text-[10px] text-text2`}>Charon</div>
      <div ref={mark("env")} className={`${base} rounded-full border border-green/60 bg-bg/85 px-2 py-0.5 font-mono text-[11px] text-green`}>.env</div>
      <div ref={mark("loot")} className={`${base} rounded-full border border-green/60 bg-bg/85 px-2.5 py-1 font-mono text-[11px] text-green`}>key #7f3a</div>
      <div ref={mark("warrior")} className={`${base} caps rounded-full bg-bg/85 px-2.5 py-1 text-[10px] font-semibold text-[rgb(120_168_255)]`}>Warrior</div>
      <div ref={mark("rotated")} className={`${base} flex items-center gap-1.5 rounded-full border border-[rgb(76_141_255/.6)] bg-bg/85 px-2.5 py-1 font-mono text-[11px] text-[rgb(120_168_255)]`}>
        <KeyRound size={12} aria-hidden /> keys rotated
      </div>
      <div ref={mark("trapped")} className={`${base} rounded-full border border-green/50 bg-bg/85 px-2.5 py-1 font-mono text-[11px] text-green`}>trapped again</div>
    </div>
  );
}
