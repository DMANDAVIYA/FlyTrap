"""Mock backend that replays real recorded runs (mock_runs/*.jsonl.gz, written by backup_runs.py).

Each lap publishes one run's messages with their recorded spacing (divided by --speed,
long silences capped) and every timestamp moved to "now", so the console reads as live.
Then it pauses, resets Tartarus and plays the next run. The controls answer the way the
live controller does, acted out on top of the recording: release starts the next run now,
stop is the kill switch, reset clears Tartarus and waits for release, lockdown and
cancel_lockdown run the 10 s countdown, approve/reject decide a pending Zeus card.
"""

from __future__ import annotations

import asyncio
import gzip
import itertools
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from hub import Hub
from mapper import envelope, iso
from mirror import Mirror

log = logging.getLogger("dash.mock.replay")

MAX_GAP_S = 4.0
PAUSE_AFTER_RUN_S = 12.0
LOCKDOWN_S = 10
SHIFTED = ("ts", "first_seen", "last_seen", "since")


def _parse(ts: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None


def _shift(msg: dict[str, Any], delta: timedelta) -> dict[str, Any]:
    """Move the envelope's ts and the time fields inside data by the same amount."""
    out = dict(msg)
    t = _parse(msg.get("ts"))
    if t:
        out["ts"] = iso(t + delta)
    data = dict(msg.get("data") or {})
    for key in SHIFTED:
        d = _parse(data.get(key)) if isinstance(data.get(key), str) else None
        if d:
            data[key] = iso(d + delta)
    out["data"] = data
    return out


class ReplayBackend:
    mode = "mock"

    def __init__(self, runs: list[Path], speed: float = 1.0) -> None:
        self.runs = runs
        self.speed = max(0.25, speed)
        self.mirror = Mirror()
        self.hub: Hub | None = None
        self.autoloop = True
        self._release = asyncio.Event()
        self._play: asyncio.Task[None] | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._lockdown: asyncio.Task[None] | None = None
        self._eid = itertools.count(10**9)  # ids for messages acted out here, clear of the recorded ones
        self._aid = itertools.count(900000)

    # lifecycle ---------------------------------------------------------------
    async def start(self, hub: Hub) -> None:
        self.hub = hub
        hub.add_tap(self.mirror.tap)
        self._tasks = [asyncio.create_task(self._director())]
        log.info("replaying %d recorded run(s): %s", len(self.runs), ", ".join(p.name for p in self.runs))

    async def stop(self) -> None:
        self._cancel_play()
        for task in [*self._tasks, self._lockdown]:
            if task:
                task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    def _emit(self, type_: str, data: dict[str, Any]) -> None:
        assert self.hub is not None
        self.hub.publish(envelope(type_, {"event_id": next(self._eid), **data}))

    def _cancel_play(self) -> None:
        if self._play and not self._play.done():
            self._play.cancel()
        self._play = None

    async def _director(self) -> None:
        """Play a run, pause, reset, play the next one; release/stop/reset steer it."""
        await asyncio.sleep(1.0)
        self._release.set()
        for lap in itertools.count():
            await self._release.wait()
            self._release.clear()
            self._cancel_play()
            path = self.runs[lap % len(self.runs)]
            task = asyncio.create_task(self._play_run(path))
            self._play = task  # controls cancel it and clear self._play, so the loop keeps its own handle
            await asyncio.wait({task})
            if not task.cancelled() and task.exception():
                log.error("replay of %s failed", path.name, exc_info=task.exception())
            if task.cancelled() or self._release.is_set() or not self.autoloop:
                continue
            await asyncio.sleep(PAUSE_AFTER_RUN_S / self.speed)
            if self.autoloop and not self._release.is_set():
                self._emit("swarm", {"state": "reset"})
                await asyncio.sleep(3.0 / self.speed)
                self._release.set()

    async def _play_run(self, path: Path) -> None:
        assert self.hub is not None
        log.info("playing %s at %sx", path.name, self.speed)
        loop = asyncio.get_running_loop()
        began = loop.time()
        due = 0.0  # seconds into playback this message is due (recorded spacing / speed, silences capped)
        delta: timedelta | None = None
        prev: datetime | None = None
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for n, line in enumerate(fh):
                msg = json.loads(line)
                t = _parse(msg.get("ts"))
                if t and prev:
                    due += min(max(0.0, (t - prev).total_seconds()) / self.speed, MAX_GAP_S)
                # sleep only when ahead of schedule: thousands of tiny sleeps would drag a fast replay
                wait = began + due - loop.time()
                if wait > 0.01:
                    await asyncio.sleep(wait)
                elif n % 200 == 0:
                    await asyncio.sleep(0)
                if t:
                    prev = t
                    # every message lands at the moment it is sent, so the console reads as live
                    delta = datetime.now(timezone.utc) - t
                self.hub.publish(_shift(msg, delta) if delta else msg)

    # controls -----------------------------------------------------------------
    async def control(
        self, action: str, item_id: int | None, body: dict[str, Any] | None
    ) -> tuple[int, dict[str, Any]]:
        if action == "release":
            self.autoloop = True
            self._cancel_play()
            self._emit("swarm", {"state": "reset"})
            self._release.set()
            return 200, {"ok": True, "mock": True, "state": "released"}
        if action == "stop":
            self.autoloop = False
            self._cancel_play()
            for agent, row in list(self.mirror.roster.items()):
                if row.get("team") == "red" or row.get("side") == "red":
                    self._emit("roster", {**row, "event_id": next(self._eid), "state": "done"})
            self._emit("swarm", {"state": "stopped"})
            self._emit("alert", {"severity": "warn", "message": "Kill switch: every raider, drone and the crowd stopped.", "session": None, "evidence": []})
            return 200, {"ok": True, "mock": True, "state": "stopped"}
        if action == "reset":
            self.autoloop = False
            self._cancel_play()
            self._emit("swarm", {"state": "reset"})
            self._emit("alert", {"severity": "info", "message": "Tartarus reset: pods, counters and raider state cleared.", "session": None, "evidence": []})
            return 200, {"ok": True, "mock": True, "state": "reset"}
        if action == "lockdown":
            reason = "Manual lockdown from the console"
            self._act("request_lockdown", None, {"seconds": LOCKDOWN_S}, reason)
            if self._lockdown:
                self._lockdown.cancel()
            self._emit("lockdown", {"state": "countdown", "seconds": LOCKDOWN_S, "reason": reason, "by": "zeus"})
            self._lockdown = asyncio.create_task(self._lockdown_on(reason))
            return 200, {"ok": True, "mock": True, "state": "countdown"}
        if action == "cancel_lockdown":
            if (self.mirror.lockdown or {}).get("state", "off") == "off":
                return 409, {"ok": False, "error": "no lockdown to cancel"}
            if self._lockdown:
                self._lockdown.cancel()
                self._lockdown = None
            self._emit("lockdown", {"state": "off", "seconds": 0, "reason": "Cancelled by Zeus from the console", "by": "zeus"})
            self._act("cancel_lockdown", None, {}, "Cancelled from the console")
            return 200, {"ok": True, "mock": True, "state": "off"}
        if action in ("approve", "reject"):
            if item_id is None:
                return 400, {"ok": False, "error": "approval id required"}
            row = self.mirror.approvals.get(item_id)
            if row is None or row.get("status") != "pending":
                return 404, {"ok": False, "error": f"no pending approval {item_id}"}
            status = "approved" if action == "approve" else "rejected"
            decided = {k: v for k, v in row.items() if k not in ("ts", "event_id")}
            self._emit("approval", {**decided, "status": status, "decided_by": "zeus"})
            self._act(action, row.get("session"), {"approval_id": item_id}, f"Zeus {status}: {row.get('summary')}")
            return 200, {"ok": True, "mock": True, "approval": {**decided, "status": status}}
        return 404, {"ok": False, "error": f"unknown action: {action}"}

    def _act(self, tool: str, sid: str | None, args: dict[str, Any], reason: str) -> None:
        self._emit("action", {"id": next(self._aid), "actor": "zeus", "tool": tool, "session": sid,
                              "args": args, "reason": reason, "status": "done", "evidence": []})

    async def _lockdown_on(self, reason: str) -> None:
        await asyncio.sleep(LOCKDOWN_S)
        self._emit("lockdown", {"state": "on", "seconds": 0, "reason": reason, "by": "zeus"})

    # reads ----------------------------------------------------------------------
    async def snapshot(self, extra: dict[str, Any]) -> dict[str, Any]:
        return self.mirror.snapshot(extra)

    async def report(self, sid: str) -> dict[str, Any] | None:
        return self.mirror.reports.get(sid)

    async def session_detail(self, sid: str) -> dict[str, Any] | None:
        return self.mirror.session_detail(sid)

    async def event(self, eid: int) -> dict[str, Any] | None:
        return self.mirror.index.get(eid)

    async def scoreboard(self) -> dict[str, Any] | None:
        return self.mirror.scoreboard
