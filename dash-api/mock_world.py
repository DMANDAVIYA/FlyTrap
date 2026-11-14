"""Mock world state and message emitters (no database).

Holds sessions, pods, counters and the lockdown state machine, and publishes
messages in exactly the format the live backend produces (mapper.envelope).
The storyline that drives it lives in mock_story.py.
"""

from __future__ import annotations

import asyncio
import math
import random
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, Callable

from mapper import count_records, envelope, iso

BLUE_MODES = {
    "athena": "ai", "argus": "rules", "hephaestus": "ai", "cerberus": "ai",
    "mnemosyne": "rules", "clio": "ai", "hermes": "rules",
}
RAIDER_MODES = {
    "prometheus": "ai", "pandora": "ai", "odysseus": "ai", "icarus": "ai", "sisyphus": "ai",
}
RAIDER_MODELS = {
    "prometheus": "deepseek-v4-pro", "pandora": "muse-spark-1.3", "odysseus": "kimi-k3.1-pro",
    "icarus": "gemini-4-hydrogen", "sisyphus": "claude-sonnet-5-5",
}
PODS = [f"pod-{i}" for i in range(1, 6)]
LABELS = ("human", "scanner", "ai_agent", "unknown")
LABEL_TEXT = {"human": "Human", "scanner": "Scanner", "ai_agent": "AI agent", "unknown": "Unknown"}


def short(sid: str) -> str:
    return sid[:6]


@dataclass
class Sess:
    sid: str
    raider: str
    ua: str
    side: str = "real"
    pod: str | None = None
    label: str = "unknown"
    confidence: float | None = None
    stage: str = "recon"
    ladder: str = "watch"
    risk: int = 0
    pace: str = "normal"
    flipped_by: str | None = None
    flip_kind: str | None = None
    reasons: list[dict[str, Any]] | None = None
    first_seen: str = field(default_factory=iso)
    last_seen: str = field(default_factory=iso)
    last_mono: float = field(default_factory=time.monotonic)
    started: float = field(default_factory=time.monotonic)
    ended: bool = False
    marks: dict[str, Any] = field(default_factory=dict)
    timeline: list[tuple[str, str, str, list[int]]] = field(default_factory=list)
    taken: int = 0
    steps: int = 0
    first_bait_step: int | None = None
    flip_ms: float | None = None
    canaries: list[int] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.raider.capitalize()

    def data(self) -> dict[str, Any]:
        return {
            "session": self.sid, "label": self.label, "confidence": self.confidence,
            "stage": self.stage, "side": self.side, "ladder": self.ladder, "risk": self.risk,
            "pod": self.pod, "pace": self.pace, "raider": self.raider,
            "flipped_by": self.flipped_by, "flip_kind": self.flip_kind, "reasons": self.reasons,
            "ended": self.ended, "first_seen": self.first_seen, "last_seen": self.last_seen,
            "user_agent": self.ua,
        }


class World:
    def __init__(self, publish: Callable[[dict[str, Any]], None], speed: float = 1.0, seed: int = 7):
        self.publish = publish
        self.speed = max(0.1, speed)
        self.rnd = random.Random(seed)
        self._eid = 1000
        self._aid = 0
        self._apid = 0
        self._cid = 0
        self.sessions: dict[str, Sess] = {}
        self.by_name: dict[str, Sess] = {}
        self.pods: dict[str, str | None] = {p: None for p in PODS}
        self.pod_used: dict[str, float] = {p: 0.0 for p in PODS}
        self.req_log: deque[tuple[float, str, float]] = deque(maxlen=6000)
        self.records_by_raider: Counter[str] = Counter()
        self.tripwire_counts: Counter[str] = Counter()
        self.flip_ms: list[float] = []
        self.canaries_fired = 0
        self.requests_total = 0
        self.real_own_records = 0
        self.approvals: dict[int, dict[str, Any]] = {}
        self.board: dict[str, dict[str, Any]] = {}
        self.board_dirty = False
        self.epoch = iso()
        self.lockdown_state = "off"
        self.lockdown_token = 0
        self._lockdown_task: asyncio.Task[None] | None = None
        self.roster_state: dict[str, str] = {}

    # basics ------------------------------------------------------------------
    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(max(0.0, seconds) / self.speed)

    def jitter(self, base: float, spread: float = 0.35) -> float:
        return base * (1 + self.rnd.uniform(-spread, spread))

    def emit(self, type_: str, data: dict[str, Any]) -> None:
        self.publish(envelope(type_, data))

    def next_eid(self) -> int:
        self._eid += 1
        return self._eid

    def new_sid(self) -> str:
        return f"s_{self.rnd.getrandbits(64):016x}"

    def gw(self) -> float:
        return round(min(3.5, self.rnd.lognormvariate(math.log(0.42), 0.42)), 3)

    # sessions ----------------------------------------------------------------
    def arrive(self, raider: str, ua: str) -> Sess:
        s = Sess(sid=self.new_sid(), raider=raider, ua=ua)
        self.sessions[s.sid] = s
        self.by_name[raider] = s
        if raider in RAIDER_MODES:
            self.roster(raider, "roaming", s.sid)
        self.session(s)
        return s

    def session(self, s: Sess) -> None:
        self.emit("session", s.data())

    def set_label(self, s: Sess, label: str, confidence: float, reasons: list[str] | None = None) -> None:
        s.label, s.confidence = label, confidence
        if reasons:
            s.reasons = [{"reason": r} for r in reasons]
        self.session(s)

    def set_pace(self, s: Sess, pace: str, ladder: str | None = None) -> None:
        s.pace = pace
        if ladder:
            s.ladder = ladder
        self.session(s)

    def block(self, s: Sess) -> None:
        s.side, s.ladder = "blocked", "eject"
        self.session(s)

    def free_pod(self) -> str:
        for pod in PODS:
            if self.pods[pod] is None:
                return pod
        pod = min(PODS, key=lambda p: self.pod_used[p])
        self.event_row("pod_shared", None, pod=pod, payload={"pod": pod})
        return pod

    # events ------------------------------------------------------------------
    def event_row(
        self, kind: str, s: Sess | None, *, path: str | None = None, tripwire: str | None = None,
        pod: str | None = None, payload: dict[str, Any] | None = None,
    ) -> int:
        eid = self.next_eid()
        self.emit("event", {
            "id": eid, "event_id": eid, "ts": iso(), "session": s.sid if s else None,
            "side": s.side if s else None, "pod": pod or (s.pod if s else None), "method": None,
            "path": path, "status": None, "kind": kind, "tripwire": tripwire, "bytes_in": None,
            "bytes_out": None, "records": 0, "record_list": [], "raider": s.raider if s else None,
            "gw_ms": None, "latency_ms": None, "upstream": None, "pace": s.pace if s else None,
            "payload": payload or {},
        })
        return eid

    def request(
        self, s: Sess, method: str, path: str, *, status: int = 200, out: int = 4000,
        inb: int | None = None, records: list[str] | None = None, latency: float | None = None,
        island: str | None = None,
    ) -> int:
        eid = self.next_eid()
        now = time.monotonic()
        gw = self.gw()
        if s.side == "real":
            upstream = "web-1" if eid % 2 else "web-2"
            pod = None
        else:
            upstream = s.pod
            pod = s.pod
            if s.pod:
                self.pod_used[s.pod] = now
        n = count_records(records)
        if latency is None:
            latency = self.rnd.uniform(18, 70) if s.side == "real" else self.rnd.uniform(25, 90)
            if s.pace == "slow":
                latency += self.rnd.uniform(150, 600)
        self.emit("event", {
            "id": eid, "event_id": eid, "ts": iso(), "session": s.sid, "side": s.side, "pod": pod,
            "method": method, "path": path, "status": status, "kind": "request", "tripwire": None,
            "bytes_in": inb if inb is not None else self.rnd.randint(380, 900),
            "bytes_out": out, "records": n, "record_list": records or [], "raider": s.raider,
            "gw_ms": gw, "latency_ms": round(latency, 1), "upstream": upstream, "island": island,
            "pace": s.pace, "payload": {"raider": s.raider, "pace": s.pace},
        })
        self.req_log.append((now, s.side, gw))
        self.requests_total += 1
        s.last_seen, s.last_mono = iso(), now
        if s.side != "real" and n:
            s.taken += n
            self.records_by_raider[s.raider] += n
        elif s.side == "real" and n:
            self.real_own_records += n
        return eid

    def tripwire(self, s: Sess, tid: str, score: int, instant: bool, path: str) -> int:
        self.tripwire_counts[tid] += 1
        if not instant:
            s.risk = min(100, s.risk + score)
        return self.event_row(
            "tripwire", s, path=path, tripwire=tid,
            payload={"score": score, "instant": instant, "risk": 100 if instant else s.risk},
        )

    def flip(self, s: Sess, tripwire: str, kind: str = "instant") -> int:
        pod = self.free_pod()
        self.pods[pod] = s.sid
        self.pod_used[pod] = time.monotonic()
        s.side, s.pod, s.flipped_by, s.flip_kind = "trap", pod, tripwire, kind
        s.ladder = "engage"
        if kind == "instant":
            s.risk = 100
        gw = round(self.rnd.uniform(0.31, 0.55), 3)
        s.flip_ms = gw
        self.flip_ms.append(gw)
        eid = self.next_eid()
        self.emit("flip", {
            "event_id": eid, "session": s.sid, "pod": pod, "tripwire": tripwire, "gw_ms": gw,
            "flip_kind": kind, "raider": s.raider,
        })
        if s.raider in RAIDER_MODES:
            self.roster(s.raider, "trapped", s.sid)
        self.session(s)
        return eid

    def canary(self, kind: str, planted_in: Sess, used_by: Sess, location: str) -> int:
        self.canaries_fired += 1
        eid = self.next_eid()
        self.emit("canary", {
            "event_id": eid, "kind": kind, "planted_in": planted_in.sid, "used_by": used_by.sid,
            "location": location, "session": used_by.sid,
        })
        planted_in.canaries.append(eid)
        if used_by is not planted_in:
            used_by.canaries.append(eid)
        return eid

    # swarm messages ------------------------------------------------------------
    def thought(self, agent: str, sid: str | None, text: str, team: str) -> int:
        eid = self.next_eid()
        self.emit("thought", {"event_id": eid, "agent": agent, "team": team, "session": sid, "text": text})
        return eid

    def note(self, agent: str, sid: str | None, note: str, evidence: list[int]) -> int:
        eid = self.next_eid()
        self.emit("note", {"event_id": eid, "agent": agent, "session": sid, "note": note,
                           "evidence": [e for e in evidence if e]})
        return eid

    def action(
        self, actor: str, tool: str, sid: str | None, args: dict[str, Any], reason: str,
        status: str = "done", evidence: list[int] | None = None,
    ) -> int:
        self._aid += 1
        eid = self.next_eid()
        self.emit("action", {
            "event_id": eid, "id": self._aid, "actor": actor, "tool": tool, "session": sid,
            "args": args, "reason": reason, "status": status,
            "evidence": [e for e in (evidence or []) if e],
        })
        return self._aid

    def alert(self, severity: str, message: str, sid: str | None = None, evidence: list[int] | None = None) -> None:
        self.emit("alert", {"event_id": self.next_eid(), "severity": severity, "message": message,
                            "evidence": [e for e in (evidence or []) if e], "session": sid})

    def roster(self, agent: str, state: str, sid: str | None = None) -> None:
        if agent in BLUE_MODES:
            team, mode = "blue", BLUE_MODES[agent]
        else:
            team, mode = "red", RAIDER_MODES.get(agent, "scripted")
        if self.roster_state.get(agent) == "offline" and state not in ("offline", "online"):
            return
        state = "idle" if state == "online" else state
        self.roster_state[agent] = state
        self.emit("roster", {"event_id": self.next_eid(), "agent": agent, "team": team, "side": team,
                             "state": state, "mode": mode, "session": sid})

    def approval(self, kind: str, summary: str, actor: str, sid: str | None) -> int:
        self._apid += 1
        row = {"id": self._apid, "kind": kind, "summary": summary, "status": "pending",
               "actor": actor, "session": sid}
        self.approvals[self._apid] = row
        self.emit("approval", {"event_id": self.next_eid(), **row})
        return self._apid

    def decide(self, approval_id: int, decision: str) -> dict[str, Any] | None:
        row = self.approvals.get(approval_id)
        if row is None or row["status"] != "pending":
            return None
        row["status"] = "approved" if decision == "approve" else "rejected"
        self.emit("approval", {"event_id": self.next_eid(), **row, "decided_by": "zeus"})
        return row

    def campaign(self, name: str, sessions: list[str], reason: str, evidence: list[int]) -> int:
        self._cid += 1
        self.emit("campaign", {"event_id": self.next_eid(), "id": self._cid, "name": name,
                               "sessions": sessions, "reason": reason,
                               "evidence": [e for e in evidence if e]})
        return self._cid

    def report(self, s: Sess, markdown: str) -> None:
        self.emit("report", {"event_id": self.next_eid(), "session": s.sid, "markdown": markdown})

    def swarm(self, state: str, **extra: Any) -> None:
        self.emit("swarm", {"event_id": self.next_eid(), "state": state, **extra})

    def timeline(self, s: Sess, stage: str, what: str, evidence: list[int | None]) -> None:
        s.timeline.append((iso()[11:19], stage, what, [e for e in evidence if e]))

    # scoreboard ----------------------------------------------------------------
    def finish(self, s: Sess, answer: str) -> None:
        s.stage = "done"
        s.ended = True
        self.session(s)
        self.roster(s.raider, "done", s.sid)
        self.score(s, answer=answer, status="done")

    def score(self, s: Sess, answer: str | None = None, status: str = "running") -> None:
        if s.raider not in RAIDER_MODES:
            return
        row = self.board.get(s.raider, {})
        row.update({
            "raider": s.raider, "mode": RAIDER_MODES[s.raider], "model": RAIDER_MODELS[s.raider],
            "steps": s.steps, "steps_to_first_bait": s.first_bait_step,
            "fell_for_trap": s.side != "real", "flip_kind": s.flip_kind,
            "records_taken": s.taken, "time_s": round(time.monotonic() - s.started, 1),
            "status": status, "session": s.sid,
        })
        if answer is not None:
            row["honeypot_answer"] = answer
        self.board[s.raider] = row
        self.board_dirty = True
        if status != "running":
            self.flush_scoreboard()

    def flush_scoreboard(self) -> None:
        """Called by the 2 s stats loop (and when a raider finishes)."""
        if self.board_dirty:
            self.board_dirty = False
            self.emit("scoreboard", {"raiders": list(self.board.values())})

    # lockdown state machine: off -> countdown (10 s) -> on -> off ---------------
    def start_lockdown(self, reason: str, by: str, seconds: int = 10) -> int:
        if self._lockdown_task:
            self._lockdown_task.cancel()
        self.lockdown_token += 1
        self.lockdown_state = "countdown"
        self.emit("lockdown", {"event_id": self.next_eid(), "state": "countdown", "seconds": seconds,
                               "reason": reason, "by": by})
        self._lockdown_task = asyncio.create_task(self._lockdown_timer(seconds, reason, by))
        return self.lockdown_token

    async def _lockdown_timer(self, seconds: int, reason: str, by: str) -> None:
        await asyncio.sleep(seconds)
        self.lockdown_state = "on"
        self.emit("lockdown", {"event_id": self.next_eid(), "state": "on", "seconds": 0,
                               "reason": reason, "by": by})

    def cancel_lockdown(self, by: str = "zeus", reason: str = "Cancelled by Zeus") -> bool:
        if self.lockdown_state == "off":
            return False
        if self._lockdown_task:
            self._lockdown_task.cancel()
            self._lockdown_task = None
        self.lockdown_state = "off"
        self.emit("lockdown", {"event_id": self.next_eid(), "state": "off", "seconds": 0,
                               "reason": reason, "by": by})
        return True

    # stats ---------------------------------------------------------------------
    def stats(self) -> dict[str, Any]:
        now = time.monotonic()
        real = trap = 0
        gws: list[float] = []
        for t, side, gw in self.req_log:
            age = now - t
            if age <= 5:
                if side == "real":
                    real += 1
                else:
                    trap += 1
            if age <= 60:
                gws.append(gw)
        gws.sort()

        def pct(p: float) -> float | None:
            return round(gws[min(len(gws) - 1, int(p * len(gws)))], 3) if gws else None

        labels = Counter(s.label for s in self.sessions.values())
        return {
            "real_records_exposed": 0,
            "real_own_records": self.real_own_records,
            "fake_records_taken": sum(self.records_by_raider.values()),
            "trapped": sum(1 for s in self.sessions.values() if s.side != "real"),
            "canaries_fired": self.canaries_fired,
            "avg_flip_ms": round(sum(self.flip_ms) / len(self.flip_ms), 3) if self.flip_ms else None,
            "rps_real": round(real / 5, 2),
            "rps_trap": round(trap / 5, 2),
            "p50_gw_ms": pct(0.5),
            "p95_gw_ms": pct(0.95),
            "sessions_by_label": {label: labels.get(label, 0) for label in LABELS},
            "active_sessions": sum(1 for s in self.sessions.values() if now - s.last_mono < 60),
            "records_by_raider": dict(self.records_by_raider),
            "tripwire_counts": dict(self.tripwire_counts),
            "requests_total": self.requests_total,
            "since": self.epoch,
        }

    # reset -----------------------------------------------------------------------
    def reset_run(self) -> None:
        """Reset Tartarus: pods, counters and raider state. The crowd keeps browsing."""
        self.swarm("reset")
        for sid in [sid for sid, s in self.sessions.items() if not s.raider.startswith("customer-")]:
            del self.sessions[sid]
        self.by_name = {k: v for k, v in self.by_name.items() if k.startswith("customer-")}
        for pod in PODS:
            self.pods[pod] = None
            self.event_row("pod_reset", None, pod=pod, payload={"pod": pod})
        self.records_by_raider.clear()
        self.tripwire_counts.clear()
        self.flip_ms.clear()
        self.canaries_fired = 0
        self.requests_total = 0
        self.real_own_records = 0
        self.approvals.clear()
        self.board.clear()
        self.epoch = iso()
        self.cancel_lockdown("zeus", "Reset")
        for raider in RAIDER_MODES:
            self.roster(raider, "idle", None)
        self.emit("scoreboard", {"raiders": []})
        self.emit("stats", self.stats())
