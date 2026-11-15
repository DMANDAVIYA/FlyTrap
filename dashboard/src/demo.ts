// In-browser replay of the recorded runs (public/demo/*.jsonl.gz) for the static site, where no dash-api runs.
// A port of dash-api/mock_replay.py: each lap plays one run with its recorded spacing (long silences capped) and
// every timestamp moved to now, so the console reads as live; then a pause, a reset and the next run. The controls
// answer the way the live controller does, acted out on top of the recording. On only when the build sets VITE_DEMO=1.
import type { Msg } from "./types";

export const DEMO = import.meta.env.VITE_DEMO === "1";
// #15 and #16 first; #3 ends in a lockdown, so it is not the first thing a visitor sees
export const DEMO_RUNS = ["20261115-042254", "20261115-043157", "20261115-013519"];

const MAX_GAP_S = 4;
const PAUSE_AFTER_RUN_S = 12;
const LOCKDOWN_S = 10;
const SHIFTED = ["ts", "first_seen", "last_seen", "since"];

type Raw = { type: string; ts?: string; data?: Record<string, unknown> };
type Row = Record<string, unknown>;
export type ControlResult = { ok: boolean; mock?: boolean; state?: string; error?: string; approval?: { status: string } };

const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((done) => {
    if (signal.aborted) return done();
    const t = window.setTimeout(done, ms);
    signal.addEventListener("abort", () => { window.clearTimeout(t); done(); }, { once: true });
  });

const runs = new Map<string, Promise<Raw[]>>();
function load(run: string): Promise<Raw[]> {
  let p = runs.get(run);
  if (!p) {
    p = (async () => {
      const r = await fetch(`/demo/${run}.jsonl.gz`);
      if (!r.ok) throw new Error(`demo run ${run}: HTTP ${r.status}`);
      const ab = await r.arrayBuffer();
      const head = new Uint8Array(ab, 0, 2);
      // a host may already have undone the gzip (Content-Encoding); inflate only real gzip bytes
      const text = head[0] === 0x1f && head[1] === 0x8b
        ? await new Response(new Blob([ab]).stream().pipeThrough(new DecompressionStream("gzip"))).text()
        : new TextDecoder().decode(ab);
      return text.split("\n").filter(Boolean).map((line) => JSON.parse(line) as Raw);
    })();
    runs.set(run, p);
    p.catch(() => runs.delete(run));
  }
  return p;
}

/** Moves the envelope's ts and the time fields inside data by the same amount. */
function shift(m: Raw, delta: number): Raw {
  const move = (v: unknown) => {
    const t = typeof v === "string" ? Date.parse(v) : NaN;
    return Number.isNaN(t) ? v : new Date(t + delta).toISOString();
  };
  const data: Row = { ...(m.data ?? {}) };
  for (const k of SHIFTED) if (k in data) data[k] = move(data[k]);
  return { ...m, ts: move(m.ts) as string | undefined, data };
}

export class DemoPlayer {
  private readonly send: (m: Msg) => void;
  private speed = 1;
  private autoloop = true;
  private lap = 0;
  private play: AbortController | null = null;
  private lockdownTimer = 0;
  private eid = 1e9; // ids for messages acted out here, clear of the recorded ones
  private aid = 900000;
  // what the console holds, for the controls to act on
  private approvals = new Map<number, Row>();
  private roster = new Map<string, Row>();
  private lockdown = "off";

  constructor(send: (m: Msg) => void) {
    this.send = send;
  }

  start() {
    const ctrl = new AbortController();
    this.play = ctrl;
    void sleep(1000, ctrl.signal).then(() => !ctrl.signal.aborted && this.next());
  }

  dispose() {
    this.play?.abort();
    this.play = null;
    window.clearTimeout(this.lockdownTimer);
  }

  private out(m: Raw) {
    const d = (m.data ?? {}) as Row;
    if (m.type === "approval") this.approvals.set(d.id as number, d);
    if (m.type === "roster") this.roster.set(d.agent as string, d);
    if (m.type === "lockdown") this.lockdown = String(d.state ?? "off");
    if (m.type === "swarm" && d.state === "reset") this.approvals.clear();
    this.send(m as unknown as Msg);
  }

  private emit(type: string, data: Row) {
    this.out({ type, ts: new Date().toISOString(), data: { event_id: this.eid++, ...data } });
  }

  private act(tool: string, session: unknown, args: Row, reason: string) {
    this.emit("action", { id: this.aid++, actor: "zeus", tool, session: session ?? null, args, reason, status: "done", evidence: [] });
  }

  /** Plays one run now (the next in turn unless named), then, when looping, pauses, resets and plays the next. */
  private next(run?: string) {
    this.play?.abort();
    const ctrl = new AbortController();
    this.play = ctrl;
    const name = run ?? DEMO_RUNS[this.lap++ % DEMO_RUNS.length];
    void (async () => {
      try {
        await this.playRun(name, ctrl.signal);
      } catch (err) {
        console.error(err);
      }
      if (ctrl.signal.aborted) return;
      if (run) this.emit("replay", { state: "stopped", run });
      if (!this.autoloop) return;
      await sleep((PAUSE_AFTER_RUN_S * 1000) / this.speed, ctrl.signal);
      if (ctrl.signal.aborted) return;
      this.emit("swarm", { state: "reset" });
      await sleep(3000 / this.speed, ctrl.signal);
      if (!ctrl.signal.aborted) this.next();
    })();
  }

  private async playRun(run: string, signal: AbortSignal) {
    const msgs = await load(run);
    const began = performance.now();
    let due = 0; // seconds into playback this message is due (recorded spacing / speed, silences capped)
    let prev: number | null = null;
    let delta: number | null = null;
    for (const m of msgs) {
      if (signal.aborted) return;
      const t = m.ts ? Date.parse(m.ts) : NaN;
      if (!Number.isNaN(t) && prev !== null) due += Math.min(Math.max(0, (t - prev) / 1000) / this.speed, MAX_GAP_S);
      const wait = began + due * 1000 - performance.now();
      if (wait > 10) await sleep(wait, signal); // sleep only when ahead of schedule
      if (signal.aborted) return;
      if (!Number.isNaN(t)) {
        prev = t;
        delta = Date.now() - t; // every message lands at the moment it is sent
      }
      this.out(delta === null ? m : shift(m, delta));
    }
  }

  // the Replay tab: one run at a chosen speed, then back to the loop with goLive()
  replay(run: string, speed: number) {
    this.autoloop = false;
    this.speed = Math.max(0.25, speed);
    this.emit("replay", { state: "started", run, speed });
    this.next(run);
  }

  goLive() {
    this.emit("replay", { state: "stopped" });
    this.speed = 1;
    this.autoloop = true;
    this.emit("swarm", { state: "reset" });
    this.next();
  }

  control(action: string): ControlResult {
    const [name, idText] = action.split("/");
    switch (name) {
      case "release":
        this.autoloop = true;
        this.emit("swarm", { state: "reset" });
        this.next();
        return { ok: true, mock: true, state: "released" };
      case "stop":
        this.autoloop = false;
        this.play?.abort();
        this.play = null;
        for (const row of this.roster.values()) {
          if (row.team === "red" || row.side === "red") this.emit("roster", { ...row, state: "done" });
        }
        this.emit("swarm", { state: "stopped" });
        this.emit("alert", { severity: "warn", message: "Kill switch: every raider, drone and the crowd stopped.", session: null, evidence: [] });
        return { ok: true, mock: true, state: "stopped" };
      case "reset":
        this.autoloop = false;
        this.play?.abort();
        this.play = null;
        this.emit("swarm", { state: "reset" });
        this.emit("alert", { severity: "info", message: "Tartarus reset: pods, counters and raider state cleared.", session: null, evidence: [] });
        return { ok: true, mock: true, state: "reset" };
      case "lockdown": {
        const reason = "Manual lockdown from the console";
        this.act("request_lockdown", null, { seconds: LOCKDOWN_S }, reason);
        window.clearTimeout(this.lockdownTimer);
        this.emit("lockdown", { state: "countdown", seconds: LOCKDOWN_S, reason, by: "zeus" });
        this.lockdownTimer = window.setTimeout(() => this.emit("lockdown", { state: "on", seconds: 0, reason, by: "zeus" }), LOCKDOWN_S * 1000);
        return { ok: true, mock: true, state: "countdown" };
      }
      case "cancel_lockdown":
        if (this.lockdown === "off") return { ok: false, error: "no lockdown to cancel" };
        window.clearTimeout(this.lockdownTimer);
        this.emit("lockdown", { state: "off", seconds: 0, reason: "Cancelled by Zeus from the console", by: "zeus" });
        this.act("cancel_lockdown", null, {}, "Cancelled from the console");
        return { ok: true, mock: true, state: "off" };
      case "approve":
      case "reject": {
        const id = Number(idText);
        const row = this.approvals.get(id);
        if (!Number.isInteger(id) || !row || row.status !== "pending") return { ok: false, error: `no pending approval ${idText ?? ""}`.trim() };
        const status = name === "approve" ? "approved" : "rejected";
        const decided = Object.fromEntries(Object.entries(row).filter(([k]) => k !== "ts" && k !== "event_id"));
        this.emit("approval", { ...decided, status, decided_by: "zeus" });
        this.act(name, row.session, { approval_id: id }, `Zeus ${status}: ${String(row.summary ?? "")}`);
        return { ok: true, mock: true, approval: { status } };
      }
      default:
        return { ok: false, error: `unknown action: ${name}` };
    }
  }
}
