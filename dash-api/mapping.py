"""events rows -> WebSocket messages (contract: plan section 6.8)."""

from __future__ import annotations

import json
from typing import Any

PLAIN = {"request", "beacon", "tripwire", "pod_reset", "pod_shared"}
PASSTHROUGH = {"note", "action", "approval", "campaign", "report", "alert", "swarm"}


def _payload(row: Any) -> dict:
    raw = row["payload"]
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return {}


def record_count(records: list[str] | None) -> int:
    total = 0
    for rec in records or []:
        _, _, ident = rec.partition(":")
        first, sep, last = ident.partition("-")
        if sep and first.isdigit() and last.isdigit():
            total += max(0, int(last) - int(first) + 1)
        else:
            total += 1
    return total


def event_data(row: Any, p: dict) -> dict:
    return {
        "id": row["id"], "ts": row["ts"].isoformat(), "session": row["session_id"], "side": row["side"],
        "pod": row["pod"], "method": row["method"], "path": row["path"], "status": row["status"],
        "kind": row["kind"], "tripwire": row["tripwire"], "raider": p.get("raider"),
        "records": record_count(row["records"]), "gw_ms": row["gw_ms"],
        "detail": p.get("detail"), "risk": p.get("risk"),
    }


def to_messages(row: Any) -> list[dict]:
    kind, p = row["kind"], _payload(row)
    sid = row["session_id"]
    if kind in PLAIN:
        return [{"type": "event", "data": event_data(row, p)}]
    if kind == "flip":
        return [
            {"type": "event", "data": event_data(row, p)},
            {"type": "flip", "data": {"session": sid, "pod": row["pod"] or p.get("pod"), "tripwire": row["tripwire"],
                                      "gw_ms": p.get("gw_ms", row["gw_ms"]), "flip_kind": p.get("flip_kind"),
                                      "raider": p.get("raider"), "event_id": row["id"]}},
        ]
    if kind == "canary":
        return [{"type": "canary", "data": {"kind": p.get("kind"), "planted_in": p.get("planted_in"),
                                            "used_by": p.get("used_by", sid), "event_id": row["id"],
                                            "location": p.get("location")}}]
    if kind == "thought":
        return [{"type": "thought", "data": {"agent": p.get("agent"), "team": p.get("team"), "session": sid,
                                             "text": p.get("text", ""), "id": row["id"]}}]
    if kind == "roster":
        return [{"type": "roster", "data": {"agent": p.get("agent"), "side": p.get("team"), "state": p.get("state"),
                                            "session": p.get("session", sid), "mode": p.get("mode")}}]
    if kind == "lockdown":
        return [{"type": "lockdown", "data": p}]
    if kind in PASSTHROUGH:
        data = {**p, "session": p.get("session", sid), "event_id": row["id"]}
        return [{"type": kind, "data": data}]
    return [{"type": "event", "data": event_data(row, p)}]
