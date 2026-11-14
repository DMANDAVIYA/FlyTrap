"""Compute the `stats` message (contract 10.7) from SQL every 2 s.

Window: everything since the latest {"kind": "swarm", "state": "reset"} event
("Reset Tartarus" zeroes the counters), or all time if there was none.

real_records_exposed (the hero number) = records the REAL side served to sessions
that are now trapped or blocked, that are customer data, and that are not the
session's own. Ownership comes from the ledger (events.records, X-Edge-Records):
records served on the session's own account pages (/account*, the login/signup
response) are "own"; any other customer record (user/invoice/token/usage...) the
real side served to it counts as exposed. Public catalog records (model, plan,
page) never count. The real app answers other customers' IDs with 403 and no
records, so this stays 0 unless the real side actually leaks.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from db import Database
from mapper import parse_records

EPOCH_0 = datetime(1970, 1, 1, tzinfo=timezone.utc)
PUBLIC_TYPES = {"model", "models", "plan", "plans", "page", "pages", "post", "doc", "docs"}
OWN_PATHS = ("/account", "/login", "/signup")
LABELS = ("human", "scanner", "ai_agent", "unknown")

SQL_EPOCH = """
SELECT max(ts) FROM events
WHERE kind = 'swarm' AND payload->>'state' = 'reset'
"""
SQL_TRAP_RECORDS = """
SELECT e.id, e.records, coalesce(s.raider, e.payload->>'raider') AS raider
FROM events e LEFT JOIN sessions s ON s.session_id = e.session_id
WHERE e.side = 'trap' AND e.records IS NOT NULL AND e.ts >= $1 AND e.id > $2
ORDER BY e.id
"""
SQL_REAL_LEDGER = """
SELECT e.session_id, e.path, e.status, e.records
FROM events e JOIN sessions s ON s.session_id = e.session_id
WHERE s.side IN ('trap', 'blocked') AND e.side = 'real'
  AND e.records IS NOT NULL AND e.ts >= $1
"""
SQL_RPS = """
SELECT side, count(*) AS n FROM events
WHERE kind = 'request' AND ts > now() - interval '5 seconds'
GROUP BY side
"""
SQL_GW = """
SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY gw_ms) AS p50,
       percentile_cont(0.95) WITHIN GROUP (ORDER BY gw_ms) AS p95
FROM events
WHERE kind = 'request' AND gw_ms IS NOT NULL AND ts > now() - interval '60 seconds'
"""
SQL_TRAPPED = """
SELECT count(*) FROM sessions WHERE side IN ('trap', 'blocked') AND last_seen >= $1
"""
SQL_CANARIES = "SELECT count(*) FROM events WHERE kind = 'canary' AND ts >= $1"
SQL_FLIP_MS = """
SELECT avg(coalesce((payload->>'gw_ms')::float8, gw_ms)) FROM events
WHERE kind = 'flip' AND ts >= $1
"""
SQL_LABELS = """
SELECT label, count(*) AS n FROM sessions
WHERE last_seen >= greatest($1, now() - interval '30 minutes')
GROUP BY label
"""
SQL_ACTIVE = "SELECT count(*) FROM sessions WHERE last_seen > now() - interval '60 seconds'"
SQL_TRIPWIRES = """
SELECT tripwire, count(*) AS n FROM events
WHERE kind = 'tripwire' AND tripwire IS NOT NULL AND ts >= $1
GROUP BY tripwire
"""
# stats_1m: a plain view, or a TimescaleDB continuous aggregate when installed
# (db/timescale.sql). date_trunc works on both.
SQL_REQUESTS_TOTAL = """
SELECT coalesce(sum(n), 0) FROM stats_1m
WHERE kind = 'request' AND bucket >= date_trunc('minute', $1::timestamptz)
"""


def classify_exposure(rows: list[Any]) -> tuple[int, int]:
    """Return (other_customers_records, own_records) from real-side ledger rows."""
    by_session: dict[str, list[Any]] = {}
    for row in rows:
        by_session.setdefault(row["session_id"], []).append(row)
    other = own = 0
    for srows in by_session.values():
        own_set: set[tuple[str, int]] = set()
        for row in srows:
            path = row["path"] or ""
            if path.startswith(OWN_PATHS):
                for typ, first, last in parse_records(row["records"]):
                    own_set.update((typ, i) for i in range(first, min(last, first + 5000) + 1))
        for row in srows:
            for typ, first, last in parse_records(row["records"]):
                if typ in PUBLIC_TYPES:
                    continue
                for i in range(first, min(last, first + 5000) + 1):
                    if (typ, i) in own_set:
                        own += 1
                    else:
                        other += 1
    return other, own


class StatsEngine:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.epoch: datetime | None = None
        self._cursor = 0
        self._fake_total = 0
        self._by_raider: Counter[str] = Counter()
        self.latest: dict[str, Any] | None = None

    async def _refresh_epoch(self) -> datetime:
        epoch = await self.db.fetchval(SQL_EPOCH) or EPOCH_0
        if epoch != self.epoch:
            self.epoch = epoch
            self._cursor = 0
            self._fake_total = 0
            self._by_raider = Counter()
        return epoch

    async def _fake_records(self, epoch: datetime) -> None:
        rows = await self.db.fetch(SQL_TRAP_RECORDS, epoch, self._cursor)
        for row in rows:
            n = sum(last - first + 1 for _, first, last in parse_records(row["records"]))
            self._fake_total += n
            self._by_raider[row["raider"] or "unknown"] += n
            self._cursor = max(self._cursor, row["id"])

    async def compute(self) -> dict[str, Any]:
        epoch = await self._refresh_epoch()
        await self._fake_records(epoch)
        other, own = classify_exposure(await self.db.fetch(SQL_REAL_LEDGER, epoch))
        rps = {r["side"]: r["n"] for r in await self.db.fetch(SQL_RPS)}
        gw = await self.db.fetchrow(SQL_GW)
        labels = {label: 0 for label in LABELS}
        for r in await self.db.fetch(SQL_LABELS, epoch):
            labels[r["label"] if r["label"] in labels else "unknown"] += r["n"]
        flip_ms = await self.db.fetchval(SQL_FLIP_MS, epoch)
        try:
            requests_total = int(await self.db.fetchval(SQL_REQUESTS_TOTAL, epoch))
        except Exception:  # continuous aggregate missing on a plain Postgres
            requests_total = None
        stats = {
            "real_records_exposed": other,
            "real_own_records": own,
            "fake_records_taken": self._fake_total,
            "trapped": await self.db.fetchval(SQL_TRAPPED, epoch),
            "canaries_fired": await self.db.fetchval(SQL_CANARIES, epoch),
            "avg_flip_ms": round(flip_ms, 3) if flip_ms is not None else None,
            "rps_real": round(rps.get("real", 0) / 5, 2),
            "rps_trap": round((rps.get("trap", 0) + rps.get("blocked", 0)) / 5, 2),
            "p50_gw_ms": round(gw["p50"], 3) if gw and gw["p50"] is not None else None,
            "p95_gw_ms": round(gw["p95"], 3) if gw and gw["p95"] is not None else None,
            "sessions_by_label": labels,
            "active_sessions": await self.db.fetchval(SQL_ACTIVE),
            "records_by_raider": dict(self._by_raider),
            "tripwire_counts": {
                r["tripwire"]: r["n"] for r in await self.db.fetch(SQL_TRIPWIRES, epoch)
            },
            "requests_total": requests_total,
            "since": epoch.isoformat() if epoch != EPOCH_0 else None,
        }
        self.latest = stats
        return stats
