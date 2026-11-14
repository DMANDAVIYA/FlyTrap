"""events-db access: a small asyncpg pool plus one LISTEN connection on events_new."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import asyncpg

log = logging.getLogger("dash.db")

CHANNEL = "events_new"


async def _init_conn(conn: asyncpg.Connection) -> None:
    for typ in ("json", "jsonb"):
        await conn.set_type_codec(typ, encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


class Database:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.pool: asyncpg.Pool | None = None
        self._listen: asyncpg.Connection | None = None
        self._notified = asyncio.Event()

    @property
    def ready(self) -> bool:
        return self.pool is not None

    async def connect(self) -> None:
        """Retry until events-db answers (compose may start us first)."""
        delay = 1.0
        while self.pool is None:
            try:
                self.pool = await asyncpg.create_pool(
                    self.dsn, min_size=1, max_size=5, init=_init_conn, command_timeout=10
                )
                log.info("connected to events-db")
            except (OSError, asyncpg.PostgresError) as exc:
                log.warning("events-db not ready (%s), retrying in %.0fs", exc, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 10.0)

    async def ensure_listener(self) -> None:
        if self._listen is not None and not self._listen.is_closed():
            return
        try:
            conn = await asyncpg.connect(self.dsn)
            await conn.add_listener(CHANNEL, self._on_notify)
            self._listen = conn
            log.info("listening on %s", CHANNEL)
        except (OSError, asyncpg.PostgresError) as exc:
            self._listen = None
            log.warning("LISTEN failed (%s); the 1 s poll still runs", exc)

    def _on_notify(self, _conn: Any, _pid: int, _channel: str, _payload: str) -> None:
        self._notified.set()

    async def wait_notify(self, timeout: float) -> None:
        try:
            await asyncio.wait_for(self._notified.wait(), timeout)
        except asyncio.TimeoutError:
            pass
        self._notified.clear()

    async def fetch(self, sql: str, *args: Any) -> list[asyncpg.Record]:
        assert self.pool is not None
        return await self.pool.fetch(sql, *args)

    async def fetchrow(self, sql: str, *args: Any) -> asyncpg.Record | None:
        assert self.pool is not None
        return await self.pool.fetchrow(sql, *args)

    async def fetchval(self, sql: str, *args: Any) -> Any:
        assert self.pool is not None
        return await self.pool.fetchval(sql, *args)

    async def close(self) -> None:
        if self._listen is not None and not self._listen.is_closed():
            await self._listen.close()
        if self.pool is not None:
            await self.pool.close()
