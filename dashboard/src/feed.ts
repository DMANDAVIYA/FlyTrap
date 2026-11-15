// Live state: /api/state snapshot + /ws messages, reduced into one object.
// On the static site (VITE_DEMO=1) the messages come from the in-browser replay in demo.ts instead.
import { useEffect, useReducer, useRef } from "react";
import { DEMO, DEMO_RUNS, DemoPlayer, type ControlResult } from "./demo";
import type {
  ApprovalData, CampaignData, CanaryData, EventData, FlipData, LockdownData, Msg, RosterData, SessionData,
  StatsData, StreamItem,
} from "./types";
import { RED } from "./types";

// dash-api targets replay at one socket by id (/ws?client=..., /api/replay?client=...).
// A fresh id per connection, so a closing socket can never unregister its replacement.
let clientId = "";
const newClientId = () => Math.random().toString(36).slice(2, 10);

export interface State {
  connected: boolean;
  mode: string;
  replay: { active: boolean; run?: string };
  stats: StatsData;
  sessions: Record<string, SessionData>;
  events: EventData[];
  red: StreamItem[];
  blue: StreamItem[];
  roster: Record<string, RosterData>;
  approvals: Record<number, ApprovalData>;
  campaigns: CampaignData[];
  canaries: CanaryData[];
  reports: Record<string, string | null>;
  lockdown: LockdownData;
  lastFlip: (FlipData & { at: number }) | null;
  flips: number;
  rps: { real: number; trap: number }[];
  /** One row per live stats message (every 2 s), for "last minute" deltas. Empty until the page has been open a while. */
  hist: Hist[];
}

export interface Hist {
  t: number; trapped: number; exposed: number; active: number; fake: number; keys: number; requests: number;
  p50: number | null; p95: number | null; flip: number | null;
}
const histOf = (st: StatsData, t: number): Hist => ({
  t, trapped: st.trapped, exposed: st.real_records_exposed, active: st.active_sessions ?? 0, fake: st.fake_records_taken,
  keys: st.canaries_fired, requests: st.requests_total ?? 0, p50: st.p50_gw_ms ?? null, p95: st.p95_gw_ms ?? null, flip: st.avg_flip_ms,
});

const EMPTY_STATS: StatsData = { real_records_exposed: 0, fake_records_taken: 0, trapped: 0, canaries_fired: 0, avg_flip_ms: null };

export const initial: State = {
  connected: false, mode: "", replay: { active: false }, stats: EMPTY_STATS, sessions: {},
  events: [], red: [], blue: [], roster: {}, approvals: {}, campaigns: [], canaries: [], reports: {},
  lockdown: { state: "off" }, lastFlip: null, flips: 0, rps: [], hist: [],
};

type Action =
  | { kind: "msg"; msg: Msg; live: boolean }
  | { kind: "batch"; msgs: Msg[] }
  | { kind: "snapshot"; snap: Snapshot }
  | { kind: "connected"; value: boolean }
  | { kind: "clear" };

// GET /api/state (dash-api snapshot.py)
export interface Snapshot {
  mode?: string; events?: Msg[]; sessions?: SessionData[]; stats?: StatsData | null; approvals?: ApprovalData[];
  campaigns?: CampaignData[]; reports?: { session: string; markdown?: string }[];
  roster?: (RosterData & { team?: string })[]; lockdown?: LockdownData | null;
}

const cap = <T,>(arr: T[], n: number) => (arr.length > n ? arr.slice(arr.length - n) : arr);
const isRed = (agent: string) => (RED as readonly string[]).includes(agent);

function apply(s: State, msg: Msg, live: boolean): State {
  const t = Date.now();
  switch (msg.type) {
    case "event":
      return { ...s, events: cap([...s.events, msg.data], 250) };
    case "flip":
      return { ...s, lastFlip: live ? { ...msg.data, at: t } : s.lastFlip, flips: s.flips + 1 };
    case "session":
      return { ...s, sessions: { ...s.sessions, [msg.data.session]: { ...s.sessions[msg.data.session], ...msg.data } } };
    case "thought": {
      const d = msg.data;
      const item: StreamItem = { kind: "thought", t, agent: d.agent, session: d.session, text: d.text };
      return d.team === "red" || isRed(d.agent) ? { ...s, red: cap([...s.red, item], 120) } : { ...s, blue: cap([...s.blue, item], 160) };
    }
    case "action": {
      const d = msg.data;
      const text = d.status === "rejected" ? `${d.tool} rejected: ${d.reason}` : `${d.tool} → ${d.reason}`;
      return { ...s, blue: cap([...s.blue, { kind: "action", t, agent: d.actor, session: d.session, text, tool: d.tool, status: d.status }], 160) };
    }
    case "note":
      return { ...s, blue: cap([...s.blue, { kind: "note", t, agent: msg.data.agent, session: msg.data.session, text: msg.data.note }], 160) };
    case "alert":
      return { ...s, blue: cap([...s.blue, { kind: "alert", t, agent: msg.data.agent || "hermes", session: msg.data.session ?? "-", text: msg.data.message, severity: msg.data.severity }], 160) };
    case "canary":
      return { ...s, canaries: cap([...s.canaries, msg.data], 50) };
    case "stats": {
      const stats = { ...s.stats, ...msg.data };
      return {
        ...s, stats,
        rps: cap([...s.rps, { real: msg.data.rps_real ?? 0, trap: msg.data.rps_trap ?? 0 }], 60),
        // only live readings: snapshot replays arrive all at once and would fake a time window
        hist: live ? cap([...s.hist, histOf(stats, t)], 90) : s.hist,
      };
    }
    case "lockdown":
      return { ...s, lockdown: msg.data };
    case "approval":
      return { ...s, approvals: { ...s.approvals, [msg.data.id]: msg.data } };
    case "campaign":
      return { ...s, campaigns: [...s.campaigns.filter((c) => c.id !== msg.data.id), msg.data] };
    case "roster":
      return { ...s, roster: { ...s.roster, [msg.data.agent]: msg.data } };
    case "swarm":
      // A reset starts a new stats window; clear the screen like dash-api does.
      return msg.data.state === "reset" && live ? { ...initial, connected: s.connected, mode: s.mode, roster: s.roster } : s;
    case "report":
      return { ...s, reports: { ...s.reports, [msg.data.session]: msg.data.markdown } };
    case "replay":
      if (msg.data.state === "started") return { ...initial, connected: s.connected, mode: s.mode, replay: { active: true, run: msg.data.run } };
      return { ...s, replay: { active: false } };
    default:
      return s;
  }
}

function reducer(s: State, a: Action): State {
  switch (a.kind) {
    case "msg":
      return apply(s, a.msg, a.live);
    case "batch":
      return a.msgs.reduce((acc, m) => apply(acc, m, false), s);
    case "connected":
      return { ...s, connected: a.value };
    case "clear":
      return { ...initial, connected: s.connected, mode: s.mode };
    case "snapshot": {
      const base: State = { ...initial, connected: s.connected, mode: a.snap.mode ?? "" };
      let next = (a.snap.events ?? []).reduce((acc, m) => apply(acc, m, false), base);
      if (a.snap.sessions) next = { ...next, sessions: Object.fromEntries(a.snap.sessions.map((x) => [x.session, x])) };
      if (a.snap.stats) next = { ...next, stats: a.snap.stats };
      if (a.snap.approvals) next = { ...next, approvals: Object.fromEntries(a.snap.approvals.map((x) => [x.id, x])) };
      if (a.snap.campaigns) next = { ...next, campaigns: a.snap.campaigns };
      if (a.snap.reports) next = { ...next, reports: { ...Object.fromEntries(a.snap.reports.map((r) => [r.session, r.markdown ?? null])), ...next.reports } };
      if (a.snap.roster) next = { ...next, roster: Object.fromEntries(a.snap.roster.map((r) => [r.agent, { ...r, side: r.side ?? r.team }])) };
      if (a.snap.lockdown) next = { ...next, lockdown: a.snap.lockdown };
      return next;
    }
  }
}

// Map animation listens here instead of re-rendering React for every request.
type Listener = (m: Msg) => void;
const listeners = new Set<Listener>();
export const onMessage = (fn: Listener) => {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
};

let socket: WebSocket | null = null;
let player: DemoPlayer | null = null;

export async function replay(run: string, speed: number) {
  if (player) return player.replay(run, speed);
  await fetch(`/api/replay?run=${encodeURIComponent(run)}&speed=${speed}&client=${clientId}`);
}
export async function goLive() {
  if (player) return player.goLive();
  await fetch(`/api/replay/stop?client=${clientId}`);
  socket?.close(); // reconnect reloads the live snapshot
}

export async function control(action: string, body: Record<string, unknown> = {}): Promise<ControlResult & Record<string, unknown>> {
  if (player) return player.control(action);
  const r = await fetch(`/api/control/${action}`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
  });
  return r.json().catch(() => ({ ok: r.ok }));
}

/** The recorded runs the Replay tab can play. */
export async function listRuns(): Promise<{ runs?: { run: string }[]; recording?: string | null }> {
  if (DEMO) return { runs: DEMO_RUNS.map((run) => ({ run })), recording: null };
  return (await fetch("/api/runs")).json();
}

export function useFeed() {
  const [state, dispatch] = useReducer(reducer, initial);
  const queue = useRef<Msg[]>([]);

  useEffect(() => {
    let closed = false;
    let retry: number | undefined;
    const take = (msg: Msg) => {
      listeners.forEach((fn) => fn(msg));
      queue.current.push(msg);
    };

    // Batch renders: at most ~12 per second, however busy the feed is.
    const flush = window.setInterval(() => {
      if (!queue.current.length) return;
      const msgs = queue.current;
      queue.current = [];
      for (const m of msgs) dispatch({ kind: "msg", msg: m, live: true });
    }, 80);

    if (DEMO) {
      dispatch({ kind: "snapshot", snap: { mode: "demo" } });
      dispatch({ kind: "connected", value: true });
      const p = new DemoPlayer(take);
      player = p;
      p.start();
      return () => {
        window.clearInterval(flush);
        p.dispose();
        if (player === p) player = null;
      };
    }

    const loadSnapshot = () =>
      fetch("/api/state").then((r) => r.json()).then((snap: Snapshot) => dispatch({ kind: "snapshot", snap })).catch(() => {});

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      clientId = newClientId();
      const ws = new WebSocket(`${proto}://${location.host}/ws?client=${clientId}`);
      socket = ws;
      ws.onopen = () => {
        dispatch({ kind: "connected", value: true });
        loadSnapshot();
      };
      ws.onmessage = (e) => take(JSON.parse(e.data) as Msg);
      ws.onclose = () => {
        dispatch({ kind: "connected", value: false });
        if (!closed) retry = window.setTimeout(connect, 1500);
      };
    };
    connect();

    return () => {
      closed = true;
      window.clearTimeout(retry);
      window.clearInterval(flush);
      socket?.close();
    };
  }, []);

  return state;
}
