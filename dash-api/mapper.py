"""Map events-table rows and sessions rows to WebSocket envelopes.

Contract: agent-context.md section 10.6 (event payloads) and 10.7 (envelope).
Every message is {"type": ..., "ts": ISO time, "data": {...}}. Messages that come
from an events row carry data.event_id so clients can de-duplicate snapshot and
live copies of the same row.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

# events.kind values that are shown as a plain "event" message
EVENT_KINDS = {"request", "tripwire", "beacon", "pod_reset", "pod_shared"}

# kinds that belong in the chat / story history kept in snapshots
STORY_KINDS = (
    "thought",
    "note",
    "action",
    "alert",
    "canary",
    "campaign",
    "flip",
    "approval",
    "report",
    "lockdown",
    "swarm",
    "tripwire",
    "pod_shared",
)

_RECORD = re.compile(r"^\s*([A-Za-z_]+)\s*:\s*(\d+)\s*(?:-\s*(\d+))?\s*$")
_MAX_TEXT = 4000


def iso(dt: datetime | None = None) -> str:
    """ISO 8601 in UTC with milliseconds and a Z suffix."""
    dt = dt or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def envelope(type_: str, data: dict[str, Any], ts: str | None = None) -> dict[str, Any]:
    return {"type": type_, "ts": ts or iso(), "data": data}


def parse_records(items: Iterable[str] | None) -> list[tuple[str, int, int]]:
    """Parse X-Edge-Records items ("user:41", "invoice:9001-9020") into (type, first, last).

    Items may themselves be comma lists. Unparseable items count as one record of
    type "other".
    """
    out: list[tuple[str, int, int]] = []
    for item in items or []:
        for part in str(item).split(","):
            if not part.strip():
                continue
            m = _RECORD.match(part)
            if not m:
                out.append(("other", 0, 0))
                continue
            first = int(m.group(2))
            last = int(m.group(3)) if m.group(3) else first
            if last < first:
                first, last = last, first
            out.append((m.group(1).lower(), first, last))
    return out


def count_records(items: Iterable[str] | None) -> int:
    return sum(last - first + 1 for _, first, last in parse_records(items))


def _sid(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value)
    return None if s in ("", "-") else s


def _payload(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("payload")
    if raw is None:
        return {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _lower(value: Any) -> str | None:
    return str(value).lower() if value is not None else None


def _text(value: Any) -> str:
    return str(value or "")[:_MAX_TEXT]


def _num(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def island_of(path: Any, payload: Mapping[str, Any] | None = None) -> str | None:
    """Which Tartarus island a pod proxied this request to (backup-01, model-vault), if any."""
    if payload and payload.get("island"):
        return str(payload["island"])
    p = str(path or "")
    if p.startswith("/internal-backup") or p.startswith("/admin/infra/backup-01"):
        return "backup-01"
    if p.startswith("/admin/infra/model-vault"):
        return "model-vault"
    return None


def event_data(row: Mapping[str, Any], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload if payload is not None else _payload(row)
    records = list(row.get("records") or [])
    side = row.get("side")
    return {
        "id": row["id"],
        "event_id": row["id"],
        "ts": iso(row["ts"]),
        "session": _sid(row.get("session_id")),
        "side": side,
        "pod": row.get("pod") or payload.get("pod"),
        "method": row.get("method"),
        "path": row.get("path"),
        "status": row.get("status"),
        "kind": row["kind"],
        "tripwire": row.get("tripwire"),
        "bytes_in": row.get("req_bytes"),
        "bytes_out": row.get("resp_bytes"),
        "records": count_records(records),
        "record_list": records[:24],
        "raider": payload.get("raider"),
        "gw_ms": _num(row.get("gw_ms")),
        "latency_ms": _num(row.get("latency_ms")),
        "upstream": payload.get("upstream"),
        "island": island_of(row.get("path"), payload) if side in ("trap", "blocked") else None,
        "pace": payload.get("pace"),
        "payload": payload,
    }


def row_to_message(row: Mapping[str, Any]) -> dict[str, Any]:
    """One events row -> one envelope. Unknown kinds become plain events."""
    kind = row["kind"]
    p = _payload(row)
    ts = iso(row["ts"])
    eid = row["id"]
    sid = _sid(row.get("session_id"))

    if kind == "flip":
        return envelope(
            "flip",
            {
                "event_id": eid,
                "session": sid,
                "pod": p.get("pod") or row.get("pod"),
                "tripwire": row.get("tripwire") or p.get("tripwire"),
                "gw_ms": _num(p.get("gw_ms", row.get("gw_ms"))),
                "flip_kind": p.get("flip_kind"),
                "raider": p.get("raider"),
            },
            ts,
        )
    if kind == "canary":
        return envelope(
            "canary",
            {
                "event_id": eid,
                "kind": p.get("kind"),
                "planted_in": p.get("planted_in"),
                "used_by": p.get("used_by") or sid,
                "location": p.get("location"),
                "session": sid,
            },
            ts,
        )
    if kind == "thought":
        return envelope(
            "thought",
            {
                "event_id": eid,
                "agent": _lower(p.get("agent")),
                "team": p.get("team"),
                "session": sid,
                "text": _text(p.get("text")),
                "model": p.get("model"),        # which model wrote this thought (absent for code-only agents)
                "persona": p.get("persona"),    # raider copies: "odysseus-2" -> "odysseus"
            },
            ts,
        )
    if kind == "note":
        return envelope(
            "note",
            {
                "event_id": eid,
                "agent": _lower(p.get("agent")),
                "session": sid,
                "note": _text(p.get("note")),
                "evidence": list(p.get("evidence") or []),
            },
            ts,
        )
    if kind == "action":
        return envelope(
            "action",
            {
                "event_id": eid,
                "id": p.get("id"),
                "actor": _lower(p.get("actor")),
                "tool": p.get("tool"),
                "session": sid,
                "args": p.get("args") or {},
                "reason": _text(p.get("reason")),
                "status": p.get("status") or "done",
                "evidence": list(p.get("evidence") or []),
            },
            ts,
        )
    if kind == "alert":
        return envelope(
            "alert",
            {
                "event_id": eid,
                "severity": p.get("severity") or "info",
                "message": _text(p.get("message")),
                "evidence": list(p.get("evidence") or []),
                "session": sid,
            },
            ts,
        )
    if kind == "campaign":
        return envelope(
            "campaign",
            {
                "event_id": eid,
                "id": p.get("id"),
                "name": p.get("name") or f"Campaign {p.get('id', '')}".strip(),
                "sessions": list(p.get("sessions") or []),
                "reason": _text(p.get("reason")),
                "evidence": list(p.get("evidence") or []),
            },
            ts,
        )
    if kind == "approval":
        return envelope(
            "approval",
            {
                "event_id": eid,
                "id": p.get("id"),
                "kind": p.get("kind"),
                "summary": _text(p.get("summary")),
                "status": p.get("status") or "pending",
                "actor": _lower(p.get("actor")),
                "session": sid,
            },
            ts,
        )
    if kind == "report":
        return envelope(
            "report",
            {"event_id": eid, "session": sid, "markdown": str(p.get("markdown") or "")},
            ts,
        )
    if kind == "roster":
        team = p.get("team") or p.get("side")
        return envelope(
            "roster",
            {
                "event_id": eid,
                "agent": _lower(p.get("agent")),
                "team": team,
                "side": team,
                "state": p.get("state"),
                "mode": p.get("mode"),
                "model": p.get("model"),
                "persona": p.get("persona"),
                "copy": p.get("copy"),
                "scope": p.get("scope"),
                "session": _sid(p.get("session")),
            },
            ts,
        )
    if kind == "lockdown":
        return envelope(
            "lockdown",
            {
                "event_id": eid,
                "state": p.get("state") or "off",
                "seconds": p.get("seconds"),
                "reason": _text(p.get("reason")),
                "by": p.get("by"),
            },
            ts,
        )
    if kind == "swarm":
        data = {"event_id": eid, **p}
        data.setdefault("state", "released")
        return envelope("swarm", data, ts)
    return envelope("event", event_data(row, p), ts)


SESSION_COLUMNS = (
    "session_id, first_seen, last_seen, side, pod, flipped_by, flip_kind, risk, pace, "
    "label, confidence, reasons, stage, ladder, raider, ended, user_agent"
)


def session_data(row: Mapping[str, Any]) -> dict[str, Any]:
    ua = row.get("user_agent")
    return {
        "session": row["session_id"],
        "label": row.get("label") or "unknown",
        "confidence": _num(row.get("confidence")),
        "stage": row.get("stage") or "recon",
        "side": row.get("side") or "real",
        "ladder": row.get("ladder") or "watch",
        "risk": int(row.get("risk") or 0),
        "pod": row.get("pod"),
        "pace": row.get("pace") or "normal",
        "raider": row.get("raider"),
        "flipped_by": row.get("flipped_by"),
        "flip_kind": row.get("flip_kind"),
        "reasons": row.get("reasons"),
        "ended": bool(row.get("ended")),
        "first_seen": iso(row["first_seen"]) if row.get("first_seen") else None,
        "last_seen": iso(row["last_seen"]) if row.get("last_seen") else None,
        "user_agent": str(ua)[:120] if ua else None,
    }
