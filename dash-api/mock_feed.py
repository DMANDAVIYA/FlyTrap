"""Mock dash-api: the SAME HTTP/WS API on port 8090, no database, looping storyline.

    python mock_feed.py                  # 127.0.0.1:8090
    python mock_feed.py --host 0.0.0.0 --speed 1.5 --no-record

Controls act on the mock: release restarts the story now, stop is the kill
switch (raiders and crowd stop), reset clears Tartarus and waits for release,
lockdown / cancel_lockdown drive the countdown, approve/reject decide cards.
The story loops by itself until you press stop or reset.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import uvicorn

from api import create_app
from hub import Hub
from mapper import envelope
from mirror import Mirror
from mock_story import Story
from mock_world import BLUE_MODES, RAIDER_MODES, World

log = logging.getLogger("dash.mock")
HERE = Path(__file__).resolve().parent
PAUSE_AFTER_RUN_S = 12.0


class MockBackend:
    mode = "mock"

    def __init__(self, speed: float = 1.0) -> None:
        self.speed = speed
        self.mirror = Mirror()
        self.hub: Hub | None = None
        self.world: World | None = None
        self.crowd: Story | None = None
        self.story: Story | None = None
        self.autoloop = True
        self._release = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []
        self._story_task: asyncio.Task[None] | None = None

    # lifecycle ---------------------------------------------------------------
    async def start(self, hub: Hub) -> None:
        self.hub = hub
        hub.add_tap(self.mirror.tap)
        self.world = World(hub.publish, speed=self.speed)
        for agent in BLUE_MODES:
            self.world.roster(agent, "idle")
        for raider in RAIDER_MODES:
            self.world.roster(raider, "idle")
        self._start_crowd()
        self._tasks = [
            asyncio.create_task(self._stats_loop()),
            asyncio.create_task(self._director()),
        ]

    async def stop(self) -> None:
        self._cancel_story()
        if self.crowd:
            self.crowd.cancel_all()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    def _start_crowd(self) -> None:
        assert self.world is not None
        if self.crowd is None:
            self.crowd = Story(self.world)
        self.crowd.start_crowd(30)

    def _cancel_story(self) -> None:
        if self.story:
            self.story.cancel_all()
        if self._story_task and not self._story_task.done():
            self._story_task.cancel()
        self._story_task = None

    async def _stats_loop(self) -> None:
        assert self.world is not None and self.hub is not None
        while True:
            await asyncio.sleep(2.0)
            self.hub.publish(envelope("stats", self.world.stats()))
            self.world.flush_scoreboard()

    async def _director(self) -> None:
        """Crowd first, then the story, looping: run, pause, reset, run again."""
        assert self.world is not None
        await self.world.sleep(5.0)
        self._release.set()
        while True:
            await self._release.wait()
            self._release.clear()
            self._cancel_story()
            self.story = Story(self.world)
            self.story.customers = self.crowd.customers if self.crowd else []
            task = asyncio.create_task(self.story.run())
            self._story_task = task
            await asyncio.wait({task})  # does not raise when "release"/"stop" cancels the run
            if task.cancelled() or self._release.is_set() or not self.autoloop:
                continue
            await self.world.sleep(PAUSE_AFTER_RUN_S)
            if self.autoloop and not self._release.is_set():
                self.story.cancel_all()
                self.world.reset_run()
                await self.world.sleep(3.0)
                self._release.set()

    # controls -----------------------------------------------------------------
    async def control(
        self, action: str, item_id: int | None, body: dict[str, Any] | None
    ) -> tuple[int, dict[str, Any]]:
        w = self.world
        assert w is not None
        if action == "release":
            self.autoloop = True
            self._start_crowd()
            self._cancel_story()
            w.reset_run()
            self._release.set()
            return 200, {"ok": True, "mock": True, "state": "released"}
        if action == "stop":
            self.autoloop = False
            self._cancel_story()
            if self.crowd:
                self.crowd.cancel_all()
            for raider in RAIDER_MODES:
                w.roster(raider, "done")
            w.swarm("stopped")
            w.alert("warn", "Kill switch: every raider, drone and the crowd stopped.")
            return 200, {"ok": True, "mock": True, "state": "stopped"}
        if action == "reset":
            self.autoloop = False
            self._cancel_story()
            w.reset_run()
            self._start_crowd()
            w.alert("info", "Tartarus reset: pods, counters and raider state cleared.")
            return 200, {"ok": True, "mock": True, "state": "reset"}
        if action == "lockdown":
            w.action("zeus", "request_lockdown", None, {"seconds": 10}, "Manual lockdown from the console")
            w.start_lockdown("Manual lockdown from the console", by="zeus")
            return 200, {"ok": True, "mock": True, "state": "countdown"}
        if action == "cancel_lockdown":
            if not w.cancel_lockdown("zeus", "Cancelled by Zeus from the console"):
                return 409, {"ok": False, "error": "no lockdown to cancel"}
            w.action("zeus", "cancel_lockdown", None, {}, "Cancelled from the console")
            return 200, {"ok": True, "mock": True, "state": "off"}
        if action in ("approve", "reject"):
            if item_id is None:
                return 400, {"ok": False, "error": "approval id required"}
            row = w.decide(item_id, action)
            if row is None:
                return 404, {"ok": False, "error": f"no pending approval {item_id}"}
            verb = "approved" if action == "approve" else "rejected"
            w.action("zeus", action, row.get("session"), {"approval_id": item_id}, f"Zeus {verb}: {row['summary']}")
            if action == "approve" and row["kind"] == "new_rule":
                w.alert("info", "Rule T13 approved by Zeus and hot-loaded into Charon.", row.get("session"))
            elif action == "approve":
                w.alert("info", f"Zeus approved: {row['summary']}", row.get("session"))
            return 200, {"ok": True, "mock": True, "approval": row}
        return 404, {"ok": False, "error": f"unknown action: {action}"}

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


def main() -> None:
    parser = argparse.ArgumentParser(description="Flytrap mock dash-api (no database)")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8090")))
    parser.add_argument("--speed", type=float, default=float(os.environ.get("MOCK_SPEED", "1.0")))
    parser.add_argument("--no-record", action="store_true", help="do not write runs/*.jsonl")
    args = parser.parse_args()
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    runs_dir = Path(os.environ.get("RUNS_DIR", HERE / "runs"))
    app = create_app(MockBackend(speed=args.speed), runs_dir, record=not args.no_record)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
