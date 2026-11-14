// Live state: /api/state snapshot + /ws messages, reduced into one object.
import { useEffect, useReducer, useRef } from "react";
import type {
  ApprovalData, CampaignData, CanaryData, EventData, FlipData, LockdownData, Msg, RosterData, SessionData,
  StatsData, StreamItem,
} from "./types";
import { RED } from "./types";

export interface State {
  connected: boolean;
  mock: boolean;
  clientId: string | null;
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
}

const EMPTY_STATS: StatsData = { real_records_exposed: 0, fake_records_taken: 0, trapped: 0, canaries_fired: 0, avg_flip_ms: null };

export const initial: State = {
  connected: false, mock: false, clientId: null, replay: { active: false }, stats: EMPTY_STATS, sessions: {},
  events: [], red: [], blue: [], roster: {}, approvals: {}, campaigns: [], canaries: [], reports: {},
  lockdown: { state: "off" }, lastFlip: null, flips: 0,
};

type Action =
  | { kind: "msg"; msg: Msg; live: boolean }
  | { kind: "batch"; msgs: Msg[] }
  | { kind: "snapshot"; snap: Snapshot }
  | { kind: "connected"; value: boolean }
  | { kind: "clear" };

export interface Snapshot {
  mock?: boolean; messages?: Msg[]; sessions?: SessionData[]; stats?: StatsData; approvals?: ApprovalData[];
  campaigns?: CampaignData[]; reports?: { session: string }[]; roster?: (RosterData & { team?: string })[];
  lockdown?: LockdownData;
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
    case "stats":
      return { ...s, stats: { ...s.stats, ...msg.data } };
    case "lockdown":
      return { ...s, lockdown: msg.data };
    case "approval":
      return { ...s, approvals: { ...s.approvals, [msg.data.id]: msg.data } };
    case "campaign":
      return { ...s, campaigns: [...s.campaigns.filter((c) => c.id !== msg.data.id), msg.data] };
    case "roster":
      return { ...s, roster: { ...s.roster, [msg.data.agent]: msg.data } };
    case "report":
      return { ...s, reports: { ...s.reports, [msg.data.session]: msg.data.markdown } };
    case "hello":
      return { ...s, clientId: msg.data.client, mock: msg.data.mock };
    case "replay":
      if (msg.data.state === "start") return { ...initial, connected: s.connected, clientId: s.clientId, mock: s.mock, replay: { active: true, run: msg.data.run } };
      return { ...s, replay: { active: false } };
    case "reset":
      return { ...initial, connected: s.connected, clientId: s.clientId, mock: s.mock, roster: s.roster };
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
      return { ...initial, connected: s.connected, clientId: s.clientId, mock: s.mock };
    case "snapshot": {
      let next = (a.snap.messages ?? []).reduce((acc, m) => apply(acc, m, false), { ...s, mock: !!a.snap.mock });
      if (a.snap.sessions) next = { ...next, sessions: Object.fromEntries(a.snap.sessions.map((x) => [x.session, x])) };
      if (a.snap.stats) next = { ...next, stats: a.snap.stats };
      if (a.snap.approvals) next = { ...next, approvals: Object.fromEntries(a.snap.approvals.map((x) => [x.id, x])) };
      if (a.snap.campaigns) next = { ...next, campaigns: a.snap.campaigns };
      if (a.snap.reports) next = { ...next, reports: { ...Object.fromEntries(a.snap.reports.map((r) => [r.session, null])), ...next.reports } };
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
export function send(msg: unknown) {
  if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(msg));
}

export async function control(action: string, body: Record<string, unknown> = {}) {
  const r = await fetch(`/api/control/${action}`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
  });
  return r.json().catch(() => ({ ok: r.ok }));
}

export function useFeed() {
  const [state, dispatch] = useReducer(reducer, initial);
  const queue = useRef<Msg[]>([]);

  useEffect(() => {
    let closed = false;
    let retry: number | undefined;

    const loadSnapshot = () =>
      fetch("/api/state").then((r) => r.json()).then((snap: Snapshot) => dispatch({ kind: "snapshot", snap })).catch(() => {});

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${proto}://${location.host}/ws`);
      socket = ws;
      ws.onopen = () => {
        dispatch({ kind: "connected", value: true });
        loadSnapshot();
      };
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data) as Msg;
        listeners.forEach((fn) => fn(msg));
        queue.current.push(msg);
      };
      ws.onclose = () => {
        dispatch({ kind: "connected", value: false });
        if (!closed) retry = window.setTimeout(connect, 1500);
      };
    };
    connect();

    // Batch renders: at most ~12 per second, however busy the feed is.
    const flush = window.setInterval(() => {
      if (!queue.current.length) return;
      const msgs = queue.current;
      queue.current = [];
      for (const m of msgs) dispatch({ kind: "msg", msg: m, live: true });
    }, 80);

    return () => {
      closed = true;
      window.clearTimeout(retry);
      window.clearInterval(flush);
      socket?.close();
    };
  }, []);

  return state;
}
