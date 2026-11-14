// WebSocket message contract (plan section 6.8).

export const BLUE = ["athena", "argus", "hephaestus", "cerberus", "mnemosyne", "clio", "hermes"] as const;
export const RED = ["prometheus", "pandora", "odysseus", "icarus", "sisyphus"] as const;

export const ROLE: Record<string, string> = {
  athena: "Commander", argus: "Watcher", hephaestus: "Builder", cerberus: "Guard", mnemosyne: "Memory",
  clio: "Historian", hermes: "Messenger",
  prometheus: "Keys and tokens", pandora: "Opens every file", odysseus: "Poses as a customer",
  icarus: "Fast and loud", sisyphus: "Walks record IDs",
};

export type Side = "real" | "trap" | "blocked";
export type Label = "unknown" | "human" | "scanner" | "ai_agent";

export interface EventData {
  id: number; ts: string; session: string; side: Side | null; pod: string | null; method: string | null;
  path: string | null; status: number | null; kind: string; tripwire: string | null; raider?: string | null;
  records?: number; gw_ms?: number | null; detail?: string | null;
}
export interface FlipData { session: string; pod: string; tripwire: string; gw_ms: number; flip_kind?: string; raider?: string | null }
export interface SessionData {
  session: string; side: Side; pod: string | null; label: Label; confidence: number | null; stage: string;
  ladder: string; risk: number; pace?: string; raider?: string | null; ended?: boolean; user_agent?: string;
  flipped_by?: string | null; reasons?: string[] | null; last_seen?: string;
}
export interface ThoughtData { agent: string; team?: string; session: string; text: string }
export interface ActionData { id: number; actor: string; tool: string; session: string; args: Record<string, unknown>; reason: string; status: string }
export interface NoteData { agent: string; session: string; note: string; evidence?: number[] }
export interface CanaryData { kind: string; planted_in: string; used_by: string; event_id: number; location?: string }
export interface StatsData {
  real_records_exposed: number; fake_records_taken: number; trapped: number; canaries_fired: number;
  avg_flip_ms: number | null; sessions?: number; gw_p50_ms?: number | null; gw_p95_ms?: number | null;
  per_minute?: { bucket: string; real?: number; trap?: number; blocked?: number }[];
}
export interface LockdownData { state: string; seconds?: number; reason?: string; by?: string }
export interface ApprovalData { id: number; kind: string; summary: string; status: string }
export interface CampaignData { id: number; name: string; sessions: string[]; reason: string; evidence?: number[] }
export interface RosterData { agent: string; side?: string; state: string; session?: string | null; mode?: string }
export interface AlertData { agent: string; severity: string; message: string; session?: string }

export type Msg =
  | { type: "event"; data: EventData }
  | { type: "flip"; data: FlipData }
  | { type: "session"; data: SessionData }
  | { type: "thought"; data: ThoughtData }
  | { type: "action"; data: ActionData }
  | { type: "note"; data: NoteData }
  | { type: "canary"; data: CanaryData }
  | { type: "stats"; data: StatsData }
  | { type: "lockdown"; data: LockdownData }
  | { type: "approval"; data: ApprovalData }
  | { type: "campaign"; data: CampaignData }
  | { type: "roster"; data: RosterData }
  | { type: "report"; data: { session: string; markdown: string } }
  | { type: "alert"; data: AlertData }
  | { type: "swarm"; data: { state: string } }
  | { type: "hello"; data: { client: string; mock: boolean; run: string } }
  | { type: "replay"; data: { state: string; run?: string; speed?: number } }
  | { type: "reset"; data: { since: string } };

export type StreamItem =
  | { kind: "thought"; t: number; agent: string; session: string; text: string }
  | { kind: "action"; t: number; agent: string; session: string; text: string; tool: string; status: string }
  | { kind: "note"; t: number; agent: string; session: string; text: string }
  | { kind: "alert"; t: number; agent: string; session: string; text: string; severity: string };
