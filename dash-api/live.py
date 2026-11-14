"""Live backend: tails events-db and turns rows into WebSocket messages.

- events: LISTEN events_new + 1 s safety poll, rows with id > last id, mapped by mapper.py.
  Ids that commit out of order (gaps) are re-checked for 10 s so nothing is missed.
- sessions: polled every 1 s, changed rows -> `session` messages.
- stats: every 2 s (stats.py).
- scoreboard: controller GET /scoreboard every 10 s, broadcast when it changes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import snapshot
from control import ControllerProxy
from db import Database
from hub import Hub
from mapper import SESSION_COLUMNS, envelope, row_to_message, session_data
from stats import EPOCH_0, StatsEngine

log = logging.getLogger("dash.live")

SQL_MAX_ID = "SELECT coalesce(max(id), 0) FROM events"
SQL_AFTER = "SELECT * FROM events WHERE id > $1 ORDER BY id LIMIT $2"
SQL_IDS = "SELECT * FROM events WHERE id = ANY($1::bigint[]) ORDER BY id"
SQL_SESSIONS_POLL = f"""
SELECT {SESSION_COLUMNS} FROM sessions
WHERE last_seen > greatest($1, now() - interval '6 hours')
ORDER BY last_seen DESC LIMIT 500
"""
BATCH = 2000
GAP_WINDOW_S = 10.0
SESSION_REFRESH_S = 15.0


class LiveBackend:
    mode = "live"

    def __init__(self, dsn: str, controller_url: str) -> None:
        self.db = Database(dsn)
        self.stats = StatsEngine(self.db)
        self.ctl = ControllerProxy(controller_url)
        self.hub: Hub | None = None
        self.last_id = 0
        self._missing: dict[int, float] = {}
        self._sessions: dict[str, tuple[str, float, str | None]] = {}
        self._scoreboard: dict[str, Any] | None = None
        self._tasks: list[asyncio.Task[None]] = []

    # lifecycle -----------------------------------------------------------
    async def start(self, hub: Hub) -> None:
        self.hub = hub
        self._tasks = [asyncio.create_task(self._run())]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.ctl.aclose()
        await self.db.close()

    async def _run(self) -> None:
        await self.db.connect()
        self.last_id = int(await self.db.fetchval(SQL_MAX_ID))
        log.info("tailing events after id %d", self.last_id)
        loops = [self._tail_loop(), self._every(1.0, self._poll_sessions)]
        loops += [self._every(2.0, self._publish_stats), self._every(10.0, self._poll_scoreboard)]
        await asyncio.gather(*loops)

    async def _every(self, seconds: float, fn: Any) -> None:
        while True:
            try:
                await fn()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("%s failed", fn.__name__)
            await asyncio.sleep(seconds)

    def _publish(self, msg: dict[str, Any]) -> None:
        assert self.hub is not None
        self.hub.publish(msg)

    # events --------------------------------------------------------------
    async def _tail_loop(self) -> None:
        while True:
            try:
                await self.db.ensure_listener()
                await self.db.wait_notify(1.0)
                await self._drain()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("tail failed")
                await asyncio.sleep(2.0)

    async def _drain(self) -> None:
        if self._missing:
            await self._recheck_missing()
        while True:
            rows = await self.db.fetch(SQL_AFTER, self.last_id, BATCH)
            prev = self.last_id
            for row in rows:
                rid = row["id"]
                if 0 < rid - prev - 1 < 1000 and prev:
                    now = time.monotonic()
                    for gap in range(prev + 1, rid):
                        self._missing.setdefault(gap, now)
                prev = rid
                self._publish(row_to_message(row))
            if rows:
                self.last_id = rows[-1]["id"]
            if len(rows) < BATCH:
                return

    async def _recheck_missing(self) -> None:
        rows = await self.db.fetch(SQL_IDS, list(self._missing))
        for row in rows:
            self._missing.pop(row["id"], None)
            self._publish(row_to_message(row))
        cutoff = time.monotonic() - GAP_WINDOW_S
        self._missing = {k: v for k, v in self._missing.items() if v > cutoff}

    # sessions / stats / scoreboard ----------------------------------------
    async def _poll_sessions(self) -> None:
        """Emit a session when any field changes; last_seen alone refreshes at most every 15 s."""
        now = time.monotonic()
        for row in await self.db.fetch(SQL_SESSIONS_POLL, self.stats.epoch or EPOCH_0):
            data = session_data(row)
            key = json.dumps({k: v for k, v in data.items() if k != "last_seen"}, default=str)
            prev = self._sessions.get(data["session"])
            if prev is not None:
                same = prev[0] == key
                seen_only = prev[2] != data["last_seen"] and now - prev[1] > SESSION_REFRESH_S
                if same and not seen_only:
                    continue
            self._sessions[data["session"]] = (key, now, data["last_seen"])
            self._publish(envelope("session", data))

    async def _publish_stats(self) -> None:
        self._publish(envelope("stats", await self.stats.compute()))

    async def _poll_scoreboard(self) -> None:
        board = await self.ctl.scoreboard()
        if board is not None and board != self._scoreboard:
            self._scoreboard = board
            self._publish(envelope("scoreboard", board))

    # HTTP API --------------------------------------------------------------
    async def snapshot(self, extra: dict[str, Any]) -> dict[str, Any]:
        if not self.db.ready:
            return snapshot.empty(extra)
        epoch = self.stats.epoch or EPOCH_0
        snap = await snapshot.build(self.db, epoch, self.stats.latest, extra)
        snap["scoreboard"] = self._scoreboard
        return snap

    async def control(
        self, action: str, item_id: int | None, body: dict[str, Any] | None
    ) -> tuple[int, dict[str, Any]]:
        return await self.ctl.call(action, item_id, body)

    async def report(self, sid: str) -> dict[str, Any] | None:
        return await snapshot.report(self.db, sid) if self.db.ready else None

    async def session_detail(self, sid: str) -> dict[str, Any] | None:
        return await snapshot.session_detail(self.db, sid) if self.db.ready else None

    async def event(self, eid: int) -> dict[str, Any] | None:
        return await snapshot.event(self.db, eid) if self.db.ready else None

    async def scoreboard(self) -> dict[str, Any] | None:
        board = await self.ctl.scoreboard()
        if board is not None:
            self._scoreboard = board
        return self._scoreboard
