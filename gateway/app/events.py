"""Event log writer.

Requests never wait on the database: events go into a bounded queue and a
background task batch-inserts them every 200 ms, then NOTIFYs consumers.
If the database is down, the queue keeps the newest events and counts drops.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import asyncpg

from .canaries import Canary
from .sessions import Session, SessionStore

log = logging.getLogger("gateway.events")

COLUMNS = (
    "ts", "session_id", "kind", "side", "pod", "src_ip", "method", "path", "query", "status",
    "req_bytes", "resp_bytes", "latency_ms", "gw_ms", "user_agent", "tripwire", "records", "payload",
)
INSERT = f"INSERT INTO events ({', '.join(COLUMNS)}) VALUES ({', '.join(f'${i}' for i in range(1, len(COLUMNS) + 1))})"
UPSERT_SESSION = """
INSERT INTO sessions (session_id, first_seen, last_seen, fingerprint, src_ip, user_agent, side, pod,
  flipped_by, flip_kind, risk, pace, label, confidence, reasons, stage, ladder, raider, ended)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
ON CONFLICT (session_id) DO UPDATE SET last_seen = EXCLUDED.last_seen, side = EXCLUDED.side, pod = EXCLUDED.pod,
  flipped_by = EXCLUDED.flipped_by, flip_kind = EXCLUDED.flip_kind, risk = EXCLUDED.risk, pace = EXCLUDED.pace,
  label = EXCLUDED.label, confidence = EXCLUDED.confidence, reasons = EXCLUDED.reasons, stage = EXCLUDED.stage,
  ladder = EXCLUDED.ladder, raider = EXCLUDED.raider, ended = EXCLUDED.ended
"""
INSERT_CANARY = """
INSERT INTO canaries (value, kind, session_id, location) VALUES ($1, $2, $3, $4)
ON CONFLICT (value) DO NOTHING
"""
FIRE_CANARY = "UPDATE canaries SET fired_at = now(), fired_by = $2 WHERE value = $1 AND fired_at IS NULL"


def _ts(epoch: float) -> datetime:
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


class EventWriter:
    def __init__(self, dsn: str, store: SessionStore) -> None:
        self.dsn = dsn
        self.store = store
        self.queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=10_000)
        self.canaries: list[Canary] = []
        self.fired: list[tuple[str, str]] = []
        self.pool: asyncpg.Pool | None = None
        self.dropped = 0

    def emit(self, kind: str, session_id: str = "-", **fields) -> None:
        event = {"kind": kind, "session_id": session_id, **fields}
        event.setdefault("ts", datetime.now(timezone.utc))
        if self.queue.full():
            self.queue.get_nowait()
            self.dropped += 1
        self.queue.put_nowait(event)

    async def connect(self) -> None:
        while self.pool is None:
            try:
                self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=4)
            except (OSError, asyncpg.PostgresError) as exc:
                log.warning("events-db not ready (%s), retrying", exc)
                await asyncio.sleep(2)

    async def run(self) -> None:
        await self.connect()
        while True:
            await asyncio.sleep(0.2)
            try:
                await self.flush()
            except (OSError, asyncpg.PostgresError) as exc:
                log.warning("flush failed: %s", exc)

    async def flush(self) -> None:
        batch = [self.queue.get_nowait() for _ in range(min(self.queue.qsize(), 2000))]
        sessions = [self.store.by_id[s] for s in list(self.store.dirty) if s in self.store.by_id]
        self.store.dirty.clear()
        canaries, self.canaries = self.canaries, []
        fired, self.fired = self.fired, []
        if not (batch or sessions or canaries or fired):
            return
        assert self.pool is not None
        async with self.pool.acquire() as conn, conn.transaction():
            if sessions:
                await conn.executemany(UPSERT_SESSION, [self._session_args(s) for s in sessions])
            if canaries:
                await conn.executemany(INSERT_CANARY, [(c.value, c.kind, c.session_id, c.location) for c in canaries])
            if fired:
                await conn.executemany(FIRE_CANARY, fired)
            if batch:
                await conn.executemany(INSERT, [self._event_args(e) for e in batch])
                last_id = await conn.fetchval("SELECT currval('events_id_seq')")
                await conn.execute(f"NOTIFY events_new, '{int(last_id)}'")

    @staticmethod
    def _event_args(e: dict) -> tuple:
        payload = e.get("payload")
        return tuple(
            json.dumps(payload) if col == "payload" and payload is not None else e.get(col)
            for col in COLUMNS
        )

    @staticmethod
    def _session_args(s: Session) -> tuple:
        r = s.row()
        return (
            r["session_id"], _ts(r["first_seen"]), _ts(r["last_seen"]), r["fingerprint"], r["src_ip"] or None,
            r["user_agent"], r["side"], r["pod"], r["flipped_by"], r["flip_kind"], r["risk"], r["pace"],
            r["label"], r["confidence"], json.dumps(r["reasons"]) if r["reasons"] is not None else None,
            r["stage"], r["ladder"], r["raider"], r["ended"],
        )

    async def load_state(self) -> tuple[list[Session], list[Canary]]:
        """Reload live sessions and canaries after a gateway restart."""
        await self.connect()
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM sessions WHERE NOT ended")
            canary_rows = await conn.fetch("SELECT value, kind, session_id, location FROM canaries")
        sessions = []
        for r in rows:
            s = Session(session_id=r["session_id"], fingerprint=r["fingerprint"] or "", src_ip=str(r["src_ip"] or ""),
                        user_agent=r["user_agent"] or "")
            s.first_seen, s.last_seen = r["first_seen"].timestamp(), r["last_seen"].timestamp()
            for key in ("side", "pod", "flipped_by", "flip_kind", "risk", "pace", "label", "confidence",
                        "stage", "ladder", "raider"):
                setattr(s, key, r[key])
            s.reasons = json.loads(r["reasons"]) if r["reasons"] else None
            sessions.append(s)
        canaries = [Canary(r["value"], r["kind"], r["session_id"], r["location"] or "") for r in canary_rows]
        return sessions, canaries

    async def approval_ok(self, approval_id: int, kind: str, session_id: str | None = None) -> bool:
        """Check Zeus really approved this action (second lock behind the controller)."""
        if self.pool is None:
            return False
        row = await self.pool.fetchrow(
            "SELECT status, kind, payload FROM approvals WHERE id = $1", approval_id
        )
        if not row or row["status"] != "approved" or row["kind"] != kind:
            return False
        if session_id is None:
            return True
        payload = json.loads(row["payload"]) if row["payload"] else {}
        return payload.get("session") == session_id

    async def fingerprints(self) -> list[dict]:
        if self.pool is None:
            return []
        rows = await self.pool.fetch(
            "SELECT DISTINCT ON (user_agent, src_ip) user_agent, src_ip FROM fingerprints ORDER BY user_agent, src_ip, created_at DESC"
        )
        return [{"user_agent": r["user_agent"] or "", "src_ip": str(r["src_ip"] or "")} for r in rows]
