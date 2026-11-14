"""In-memory mirror of the message stream, used by the mock to answer /api/state
and the detail endpoints without a database. It is fed every published message."""

from __future__ import annotations

from collections import OrderedDict, deque
from datetime import datetime, timezone
from typing import Any

from mapper import iso

EVENT_DERIVED = {
    "event", "flip", "canary", "thought", "note", "action", "alert",
    "campaign", "approval", "report", "roster", "lockdown", "swarm",
}
STORY = EVENT_DERIVED - {"event", "roster"}
INDEX_MAX = 30000
HISTORY_MINUTES = 30


def _minute(ts: str | None) -> str:
    """ISO ts -> start of its UTC minute, same shape as the live stats_1m buckets."""
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        dt = datetime.now(timezone.utc)
    return iso(dt.replace(second=0, microsecond=0))


class Mirror:
    def __init__(self) -> None:
        self.events: deque[dict[str, Any]] = deque(maxlen=200)
        self.story: deque[dict[str, Any]] = deque(maxlen=300)
        self.loot: deque[dict[str, Any]] = deque(maxlen=300)
        self.index: OrderedDict[int, dict[str, Any]] = OrderedDict()
        self.by_session: dict[str, deque[dict[str, Any]]] = {}
        self.sessions: dict[str, dict[str, Any]] = {}
        self.approvals: dict[Any, dict[str, Any]] = {}
        self.roster: dict[str, dict[str, Any]] = {}
        self.campaigns: dict[Any, dict[str, Any]] = {}
        self.reports: dict[str, dict[str, Any]] = {}
        self.canaries: list[dict[str, Any]] = []
        self.lockdown: dict[str, Any] | None = None
        self.swarm: dict[str, Any] | None = None
        self.stats: dict[str, Any] | None = None
        self.scoreboard: dict[str, Any] | None = None
        # requests per (minute, side), like the live snapshot's `history` from stats_1m
        self.history: OrderedDict[tuple[str, str], int] = OrderedDict()

    def tap(self, msg: dict[str, Any], _text: str) -> None:
        self.apply(msg)

    def apply(self, msg: dict[str, Any]) -> None:
        t, d, ts = msg["type"], msg.get("data") or {}, msg.get("ts")
        eid = d.get("event_id")
        if t in EVENT_DERIVED:
            self.events.append(msg)
            if eid is not None:
                self.index[eid] = msg
                if len(self.index) > INDEX_MAX:
                    self.index.popitem(last=False)
            # roster rows are written with session "-" in the live log, so keep them out of drawers
            sids = set() if t == "roster" else {d.get("session"), d.get("used_by"), d.get("planted_in")} - {None}
            for sid in sids:
                self.by_session.setdefault(sid, deque(maxlen=400)).append(msg)
        if t in STORY:
            self.story.append(msg)
        if t == "event" and d.get("kind") == "request" and d.get("side"):
            self._count(ts, d["side"])
        if t == "event" and d.get("side") in ("trap", "blocked"):
            if (d.get("records") or 0) > 0 or (d.get("bytes_out") or 0) > 50000:
                self.loot.append(msg)
        if t == "session":
            self.sessions[d["session"]] = d
        elif t == "approval":
            self.approvals[d.get("id")] = {**d, "ts": ts}
        elif t == "roster" and d.get("agent"):
            self.roster[d["agent"]] = d
        elif t == "campaign":
            self.campaigns[d.get("id")] = {**d, "ts": ts}
        elif t == "report" and d.get("session"):
            self.reports[d["session"]] = {"session": d["session"], "markdown": d.get("markdown", ""), "ts": ts}
        elif t == "canary":
            self.canaries.append({**d, "ts": ts})
        elif t == "lockdown":
            self.lockdown = {**d, "ts": ts}
        elif t == "swarm":
            self.swarm = d
            if d.get("state") == "reset":
                self.reset_run()
        elif t == "stats":
            self.stats = d
        elif t == "scoreboard":
            self.scoreboard = d

    def _count(self, ts: str | None, side: str) -> None:
        key = (_minute(ts), side)
        self.history[key] = self.history.get(key, 0) + 1
        while len(self.history) > HISTORY_MINUTES * 3:
            self.history.popitem(last=False)

    def reset_run(self) -> None:
        """Reset Tartarus: forget trapped sessions, raiders, drones and per-run findings; keep the crowd."""
        gone = {
            sid for sid, s in self.sessions.items()
            if s.get("side") != "real" or not str(s.get("raider") or "customer-").startswith("customer-")
        }
        for sid in gone:
            self.sessions.pop(sid, None)
            self.by_session.pop(sid, None)
        self.loot.clear()
        self.approvals.clear()
        self.campaigns.clear()
        self.reports.clear()
        self.canaries.clear()

    def snapshot(self, extra: dict[str, Any]) -> dict[str, Any]:
        merged: dict[Any, dict[str, Any]] = {}
        for msg in [*self.events, *self.story]:
            key = msg["data"].get("event_id") or id(msg)
            merged[key] = msg
        events = sorted(merged.values(), key=lambda m: (m["data"].get("event_id") or 0, m["ts"]))
        return {
            **extra,
            "server_time": iso(),
            "stats": self.stats,
            "sessions": list(self.sessions.values()),
            "events": events,
            "loot": list(self.loot),
            "approvals": list(self.approvals.values()),
            "roster": list(self.roster.values()),
            "campaigns": list(self.campaigns.values()),
            "lockdown": self.lockdown,
            "swarm": self.swarm,
            "reports": list(self.reports.values()),
            "scoreboard": self.scoreboard,
            "history": [{"t": t, "side": side, "n": n} for (t, side), n in self.history.items()],
        }

    def session_detail(self, sid: str) -> dict[str, Any] | None:
        session = self.sessions.get(sid)
        if session is None:
            return None
        rep = self.reports.get(sid)
        return {
            "session": session,
            "events": list(self.by_session.get(sid, [])),
            "canaries": [
                {
                    "value": None,
                    "kind": c.get("kind"),
                    "planted_in": c.get("planted_in"),
                    "location": c.get("location"),
                    "planted_at": None,
                    "fired_at": c.get("ts"),
                    "fired_by": c.get("used_by"),
                    "event_id": c.get("event_id"),
                }
                for c in self.canaries
                if sid in (c.get("planted_in"), c.get("used_by"))
            ],
            "report": rep["markdown"] if rep else None,
        }
