"""SQL behind GET /api/state and the detail endpoints (live mode)."""

from __future__ import annotations

from typing import Any

from db import Database
from mapper import SESSION_COLUMNS, STORY_KINDS, envelope, iso, row_to_message, session_data

SQL_LAST_EVENTS = "SELECT * FROM events ORDER BY id DESC LIMIT $1"
SQL_STORY = "SELECT * FROM events WHERE kind = ANY($1::text[]) AND ts >= $2 ORDER BY id DESC LIMIT $3"
SQL_LOOT = """
SELECT * FROM events
WHERE side IN ('trap', 'blocked') AND kind = 'request' AND ts >= $1
  AND (cardinality(records) > 0 OR resp_bytes > 50000)
ORDER BY id DESC LIMIT 300
"""
SQL_SESSIONS = f"""
SELECT {SESSION_COLUMNS} FROM sessions
WHERE last_seen > greatest($1, now() - interval '6 hours')
ORDER BY last_seen DESC LIMIT 500
"""
SQL_APPROVALS = """
SELECT a.id, a.ts, a.kind, a.summary, a.status, a.decided_by, a.decided_at,
       ac.actor, ac.session_id
FROM approvals a LEFT JOIN actions ac ON ac.id = a.action_id
WHERE a.status = 'pending' OR a.ts > now() - interval '30 minutes'
ORDER BY a.id DESC LIMIT 40
"""
SQL_ROSTER = """
SELECT DISTINCT ON (payload->>'agent') * FROM events
WHERE kind = 'roster' AND ts > now() - interval '12 hours'
ORDER BY payload->>'agent', id DESC
"""
SQL_CAMPAIGNS = """
SELECT id, created_at, name, session_ids, reason, evidence FROM campaigns
WHERE created_at >= $1 ORDER BY id
"""
SQL_LATEST_KIND = "SELECT * FROM events WHERE kind = $1 ORDER BY id DESC LIMIT 1"
SQL_REPORTS = """
SELECT session_id, created_at, markdown FROM reports
WHERE created_at >= $1 ORDER BY created_at DESC LIMIT 20
"""
SQL_REPORT = "SELECT session_id, created_at, markdown, report FROM reports WHERE session_id = $1"
SQL_SESSION = f"SELECT {SESSION_COLUMNS} FROM sessions WHERE session_id = $1"
SQL_SESSION_EVENTS = "SELECT * FROM events WHERE session_id = $1 ORDER BY id DESC LIMIT 400"
SQL_SESSION_CANARIES = """
SELECT value, kind, session_id, location, planted_at, fired_at, fired_by, fired_event
FROM canaries WHERE session_id = $1 OR fired_by = $1 ORDER BY planted_at
"""
SQL_EVENT = "SELECT * FROM events WHERE id = $1 LIMIT 1"
SQL_HISTORY = """
SELECT bucket, side, sum(n) AS n FROM stats_1m
WHERE kind = 'request' AND bucket > now() - interval '30 minutes'
GROUP BY bucket, side ORDER BY bucket
"""


def _approval(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "kind": row["kind"],
        "summary": row["summary"],
        "status": row["status"],
        "actor": row["actor"],
        "session": row["session_id"],
        "ts": iso(row["ts"]),
        "decided_by": row["decided_by"],
    }


def _campaign(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "sessions": list(row["session_ids"] or []),
        "reason": row["reason"],
        "evidence": list(row["evidence"] or []),
        "ts": iso(row["created_at"]),
    }


def _mask_canary(value: str) -> str:
    return value if len(value) <= 12 else value[:10] + "…" + value[-3:]


async def build(
    db: Database, epoch: Any, stats: dict[str, Any] | None, extra: dict[str, Any]
) -> dict[str, Any]:
    last = await db.fetch(SQL_LAST_EVENTS, 200)
    story = await db.fetch(SQL_STORY, list(STORY_KINDS), epoch, 300)
    rows = {r["id"]: r for r in [*last, *story]}
    events = [row_to_message(rows[i]) for i in sorted(rows)]
    loot = [row_to_message(r) for r in reversed(await db.fetch(SQL_LOOT, epoch))]
    roster = [row_to_message(r)["data"] for r in await db.fetch(SQL_ROSTER)]
    lockdown_row = await db.fetchrow(SQL_LATEST_KIND, "lockdown")
    swarm_row = await db.fetchrow(SQL_LATEST_KIND, "swarm")
    lockdown = None
    if lockdown_row:
        msg = row_to_message(lockdown_row)
        lockdown = {**msg["data"], "ts": msg["ts"]}
    try:
        history = [
            {"t": iso(r["bucket"]), "side": r["side"], "n": r["n"]}
            for r in await db.fetch(SQL_HISTORY)
        ]
    except Exception:
        history = []
    return {
        **extra,
        "server_time": iso(),
        "stats": stats,
        "sessions": [session_data(r) for r in await db.fetch(SQL_SESSIONS, epoch)],
        "events": events,
        "loot": loot,
        "approvals": [_approval(r) for r in await db.fetch(SQL_APPROVALS)],
        "roster": roster,
        "campaigns": [_campaign(r) for r in await db.fetch(SQL_CAMPAIGNS, epoch)],
        "lockdown": lockdown,
        "swarm": row_to_message(swarm_row)["data"] if swarm_row else None,
        "reports": [
            {"session": r["session_id"], "markdown": r["markdown"], "ts": iso(r["created_at"])}
            for r in await db.fetch(SQL_REPORTS, epoch)
        ],
        "history": history,
    }


async def report(db: Database, sid: str) -> dict[str, Any] | None:
    row = await db.fetchrow(SQL_REPORT, sid)
    if not row:
        return None
    return {
        "session": row["session_id"],
        "markdown": row["markdown"],
        "report": row["report"],
        "ts": iso(row["created_at"]),
    }


async def session_detail(db: Database, sid: str) -> dict[str, Any] | None:
    row = await db.fetchrow(SQL_SESSION, sid)
    if not row:
        return None
    events = [row_to_message(r) for r in reversed(await db.fetch(SQL_SESSION_EVENTS, sid))]
    canaries = [
        {
            "value": _mask_canary(r["value"]),
            "kind": r["kind"],
            "planted_in": r["session_id"],
            "location": r["location"],
            "planted_at": iso(r["planted_at"]),
            "fired_at": iso(r["fired_at"]) if r["fired_at"] else None,
            "fired_by": r["fired_by"],
            "event_id": r["fired_event"],
        }
        for r in await db.fetch(SQL_SESSION_CANARIES, sid)
    ]
    rep = await report(db, sid)
    return {
        "session": session_data(row),
        "events": events,
        "canaries": canaries,
        "report": rep["markdown"] if rep else None,
    }


async def event(db: Database, eid: int) -> dict[str, Any] | None:
    row = await db.fetchrow(SQL_EVENT, eid)
    return row_to_message(row) if row else None


def empty(extra: dict[str, Any]) -> dict[str, Any]:
    """Snapshot while events-db is unreachable."""
    return {
        **extra,
        "server_time": iso(),
        "stats": None,
        "sessions": [],
        "events": [envelope("alert", {"severity": "warn", "message": "Waiting for events-db…"})],
        "loot": [],
        "approvals": [],
        "roster": [],
        "campaigns": [],
        "lockdown": None,
        "swarm": None,
        "reports": [],
        "history": [],
    }
