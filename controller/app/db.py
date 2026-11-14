"""Events database access. Every write the swarm makes also lands in the
append-only `events` log, so the dashboard and replay see one stream."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import asyncpg

log = logging.getLogger("controller.db")


def _j(value: Any) -> str | None:
    return None if value is None else json.dumps(value)


class DB:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        while self.pool is None:
            try:
                self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=8)
            except (OSError, asyncpg.PostgresError) as exc:
                log.warning("events-db not ready (%s), retrying", exc)
                await asyncio.sleep(2)

    @property
    def p(self) -> asyncpg.Pool:
        assert self.pool is not None, "db not connected"
        return self.pool

    # ---- the log ----------------------------------------------------------
    async def emit(self, kind: str, payload: dict, session_id: str = "-", **cols: Any) -> int:
        async with self.p.acquire() as conn:
            event_id = await conn.fetchval(
                "INSERT INTO events (session_id, kind, side, pod, tripwire, payload) VALUES ($1,$2,$3,$4,$5,$6) RETURNING id",
                session_id or "-", kind, cols.get("side"), cols.get("pod"), cols.get("tripwire"), _j(payload),
            )
            await conn.execute(f"NOTIFY events_new, '{int(event_id)}'")
        return int(event_id)

    async def events_since(self, last_id: int, kinds: tuple[str, ...], limit: int = 500) -> list[asyncpg.Record]:
        return await self.p.fetch(
            "SELECT id, ts, session_id, kind, side, pod, tripwire, path, payload FROM events "
            "WHERE id > $1 AND kind = ANY($2) ORDER BY id LIMIT $3", last_id, list(kinds), limit,
        )

    async def max_event_id(self) -> int:
        return int(await self.p.fetchval("SELECT COALESCE(max(id), 0) FROM events"))

    # ---- state tables -----------------------------------------------------
    async def insert_action(self, actor: str, tool: str, session_id: str | None, args: dict, reason: str,
                            evidence: list[int], status: str) -> int:
        return int(await self.p.fetchval(
            "INSERT INTO actions (actor, tool, session_id, args, reason, evidence, status) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id", actor, tool, session_id, _j(args), reason, evidence, status,
        ))

    async def set_action_status(self, action_id: int, status: str) -> None:
        await self.p.execute("UPDATE actions SET status = $2 WHERE id = $1", action_id, status)

    async def insert_note(self, agent: str, session_id: str | None, note: str, evidence: list[int]) -> None:
        await self.p.execute("INSERT INTO agent_notes (agent, session_id, note, evidence) VALUES ($1,$2,$3,$4)",
                             agent, session_id, note, evidence)

    async def recent_notes(self, limit: int = 20) -> list[dict]:
        rows = await self.p.fetch("SELECT agent, session_id, note, evidence FROM agent_notes ORDER BY id DESC LIMIT $1", limit)
        return [dict(r) for r in reversed(rows)]

    async def insert_campaign(self, name: str, sessions: list[str], reason: str, evidence: list[int]) -> int:
        return int(await self.p.fetchval(
            "INSERT INTO campaigns (name, session_ids, reason, evidence) VALUES ($1,$2,$3,$4) RETURNING id",
            name, sessions, reason, evidence))

    async def campaigns(self) -> list[dict]:
        rows = await self.p.fetch("SELECT id, name, session_ids, reason FROM campaigns ORDER BY id")
        return [dict(r) for r in rows]

    async def insert_approval(self, kind: str, summary: str, payload: dict, action_id: int | None) -> int:
        return int(await self.p.fetchval(
            "INSERT INTO approvals (kind, action_id, summary, payload) VALUES ($1,$2,$3,$4) RETURNING id",
            kind, action_id, summary, _j(payload)))

    async def get_approval(self, approval_id: int) -> dict | None:
        row = await self.p.fetchrow("SELECT * FROM approvals WHERE id = $1", approval_id)
        if not row:
            return None
        data = dict(row)
        data["payload"] = json.loads(data["payload"]) if data["payload"] else {}
        return data

    async def decide_approval(self, approval_id: int, status: str, by: str) -> None:
        await self.p.execute("UPDATE approvals SET status = $2, decided_by = $3, decided_at = now() WHERE id = $1",
                             approval_id, status, by)

    async def pending_approvals(self) -> list[dict]:
        rows = await self.p.fetch("SELECT id, kind, summary, payload, ts FROM approvals WHERE status = 'pending' ORDER BY id")
        return [{**dict(r), "payload": json.loads(r["payload"]) if r["payload"] else {}} for r in rows]

    async def insert_report(self, session_id: str, report: dict, markdown: str) -> None:
        await self.p.execute(
            "INSERT INTO reports (session_id, report, markdown) VALUES ($1,$2,$3) "
            "ON CONFLICT (session_id) DO UPDATE SET report = EXCLUDED.report, markdown = EXCLUDED.markdown, created_at = now()",
            session_id, _j(report), markdown)

    async def has_report(self, session_id: str) -> bool:
        return bool(await self.p.fetchval("SELECT 1 FROM reports WHERE session_id = $1", session_id))

    async def insert_fingerprint(self, session_id: str, user_agent: str, src_ip: str | None, path_signature: str,
                                 timing: dict) -> None:
        await self.p.execute(
            "INSERT INTO fingerprints (session_id, user_agent, src_ip, path_signature, timing) VALUES ($1,$2,$3,$4,$5)",
            session_id, user_agent, src_ip or None, path_signature, _j(timing))

    async def clear_fingerprints(self) -> None:
        """Reset Tartarus: forget remembered attackers so the next demo run starts fresh."""
        await self.p.execute("DELETE FROM fingerprints")

    async def expire_pending_approvals(self) -> None:
        """Reset Tartarus: requests from a previous run no longer apply."""
        await self.p.execute("UPDATE approvals SET status = 'expired', decided_at = now() WHERE status = 'pending'")

    async def existing_event_ids(self, ids: list[int]) -> set[int]:
        if not ids:
            return set()
        rows = await self.p.fetch("SELECT id FROM events WHERE id = ANY($1)", ids)
        return {int(r["id"]) for r in rows}
