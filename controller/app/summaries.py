"""Compact per-session summaries built from the event log (what the swarm reads)."""

from __future__ import annotations

import json
import re
import statistics

from . import records
from .db import DB

TOOL_UA = re.compile(r"python-|httpx|curl/|wget/|go-http|sqlmap|nikto|nmap|ffuf|nuclei|gobuster|aiohttp", re.I)
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

SESSIONS_SQL = """
SELECT * FROM sessions
WHERE NOT ended AND (last_seen > now() - interval '3 minutes' OR side <> 'real')
ORDER BY last_seen DESC LIMIT 60
"""
# Newest events per session, not overall: with a crowd and drones running, a global cap let busy
# visitors push quiet ones out, and Argus scored raiders from fragments.
EVENTS_SQL = """
SELECT e.* FROM unnest($1::text[]) AS s(session_id)
CROSS JOIN LATERAL (
    SELECT id, ts, session_id, kind, side, path, status, tripwire, records, payload, resp_bytes
    FROM events WHERE events.session_id = s.session_id AND ts > now() - interval '15 minutes'
    ORDER BY ts DESC LIMIT 400
) e
"""


PAUSE_S = 1.5  # longer than any scripted scanner wait, shorter than a model thinking about its next step


def visitor_text(value: str) -> str:
    """Attacker-controlled text: cut short and stripped before any model sees it."""
    return CONTROL_CHARS.sub(" ", value or "")[:120]


def summarize(row, events: list) -> dict:
    events = sorted(events, key=lambda e: e["id"])
    requests = [e for e in events if e["kind"] == "request"]
    times = [e["ts"].timestamp() for e in requests[-60:]]
    gaps = [b - a for a, b in zip(times, times[1:])]
    pauses = [g for g in gaps if g >= PAUSE_S]  # time spent thinking between bursts of requests
    tripwires = [{"id": e["tripwire"], "event": e["id"]} for e in events if e["kind"] == "tripwire"][-10:]
    beacons = [json.loads(e["payload"] or "{}") for e in events if e["kind"] == "beacon"]
    note_hit = next((e for e in events if e["kind"] == "tripwire" and e["tripwire"] == "T7"), None)
    followed = None
    if note_hit:
        page = next((e for e in reversed(requests) if e["id"] < note_hit["id"] and e["path"] == "/"), None)
        followed = {"event": note_hit["id"],
                    "seconds_after_page": round(note_hit["ts"].timestamp() - page["ts"].timestamp(), 1) if page else None}
    taken = records.by_type(rec for e in requests if e["side"] in ("trap", "blocked") for rec in (e["records"] or []))
    real_records = [rec for e in requests if e["side"] == "real" for rec in (e["records"] or [])]
    canaries = [{"event": e["id"], **json.loads(e["payload"] or "{}")} for e in events if e["kind"] == "canary"]
    ua = row["user_agent"] or ""
    return {
        "session": row["session_id"], "raider": row["raider"], "side": row["side"], "pod": row["pod"],
        "flipped_by": row["flipped_by"], "flip_kind": row["flip_kind"],
        "label": row["label"], "confidence": row["confidence"], "risk": row["risk"],
        "stage": row["stage"], "ladder": row["ladder"], "pace": row["pace"],
        "src_ip": str(row["src_ip"] or ""),
        "last_seen": row["last_seen"].timestamp(),
        "requests_total": len(requests),
        "requests_2min": sum(1 for t in times if times and times[-1] - t <= 120),
        "median_gap_s": round(statistics.median(gaps), 2) if gaps else None,
        "gap_spread_s": round(statistics.pstdev(gaps), 2) if len(gaps) > 1 else None,
        "pauses": len(pauses),
        "pause_share": round(len(pauses) / len(gaps), 2) if gaps else None,
        "median_pause_s": round(statistics.median(pauses), 1) if pauses else None,
        "js_beacon": bool(beacons),
        "mouse_keys": sum(b.get("mouse", 0) + b.get("keys", 0) for b in beacons),
        "assets_loaded": sum(1 for e in requests if (e["path"] or "").startswith("/static/")),
        "not_found": sum(1 for e in requests if e["status"] == 404),
        "forbidden": sum(1 for e in requests if e["status"] == 403),
        "tripwires": tripwires,
        "followed_ai_note": followed,
        "recent_paths": [e["path"] for e in requests[-8:]],
        "records_taken": dict(taken),
        "real_records_served": real_records[:50],
        "canaries_fired": canaries[-5:],
        "tool_user_agent": bool(TOOL_UA.search(ua)),
        "visitor_text": {"user_agent": visitor_text(ua)},
        "first_event": events[0]["id"] if events else None,
        "last_event": events[-1]["id"] if events else None,
    }


async def active_summaries(db: DB) -> list[dict]:
    rows = await db.p.fetch(SESSIONS_SQL)
    if not rows:
        return []
    events = await db.p.fetch(EVENTS_SQL, [r["session_id"] for r in rows])
    by_session: dict[str, list] = {}
    for e in events:
        by_session.setdefault(e["session_id"], []).append(e)
    return [summarize(r, by_session.get(r["session_id"], [])) for r in rows]
