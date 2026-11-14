"""HTTP + WebSocket API shared by the live backend (main.py) and the mock (mock_feed.py).

Routes (contract 6.7):
  GET  /healthz
  GET  /api/state                      snapshot
  WS   /ws?client=<id>                 live messages (10.7 envelope)
  GET  /api/runs                       recorded runs
  GET  /api/replay?run=..&speed=1|4&client=<id>   switch that socket into replay
  GET  /api/replay/stop?client=<id>    back to live
  POST /api/control/{action}[/{id}]    release, stop, reset, lockdown, cancel_lockdown, approve/{id}, reject/{id}
  GET  /api/reports/{sid}
  GET  /api/scoreboard
  GET  /api/sessions/{sid}             session drawer: row, events, canaries, report
  GET  /api/events/{id}                one event (evidence links)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Protocol

from fastapi import Body, FastAPI, HTTPException, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import replay
from hub import Hub
from recorder import Recorder, list_runs, run_path

log = logging.getLogger("dash.api")


class Backend(Protocol):
    mode: str

    async def start(self, hub: Hub) -> None: ...
    async def stop(self) -> None: ...
    async def snapshot(self, extra: dict[str, Any]) -> dict[str, Any]: ...
    async def control(
        self, action: str, item_id: int | None, body: dict[str, Any] | None
    ) -> tuple[int, dict[str, Any]]: ...
    async def report(self, sid: str) -> dict[str, Any] | None: ...
    async def session_detail(self, sid: str) -> dict[str, Any] | None: ...
    async def event(self, eid: int) -> dict[str, Any] | None: ...
    async def scoreboard(self) -> dict[str, Any] | None: ...


def create_app(backend: Backend, runs_dir: Path, record: bool = True) -> FastAPI:
    hub = Hub()
    recorder = Recorder(runs_dir, enabled=record)
    hub.add_tap(recorder.tap)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await backend.start(hub)
        log.info("dash-api up in %s mode", backend.mode)
        try:
            yield
        finally:
            await backend.stop()
            recorder.close()

    app = FastAPI(title="Flytrap dash-api", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )
    app.state.hub = hub
    app.state.recorder = recorder

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {"ok": True, "mode": backend.mode, "clients": len(hub.clients)}

    @app.get("/api/state")
    async def state() -> dict[str, Any]:
        return await backend.snapshot({"mode": backend.mode, "run_id": recorder.run_id})

    @app.websocket("/ws")
    async def ws(websocket: WebSocket, client: str | None = None) -> None:
        await hub.serve(websocket, client)

    @app.get("/api/runs")
    async def runs() -> dict[str, Any]:
        return {"runs": list_runs(runs_dir), "recording": recorder.run_id}

    @app.get("/api/replay")
    async def start_replay(
        run: str, speed: float = Query(1.0), client: str | None = None
    ) -> dict[str, Any]:
        if run == "live":
            return {"ok": True, "stopped": replay.stop(hub, client)}
        path = run_path(runs_dir, run)
        if path is None:
            raise HTTPException(404, f"no such run: {run}")
        n = replay.start(hub, client, path, run, speed)
        return {"ok": n > 0, "run": run, "speed": speed, "clients": n}

    @app.get("/api/replay/stop")
    async def stop_replay(client: str | None = None) -> dict[str, Any]:
        return {"ok": True, "stopped": replay.stop(hub, client)}

    async def _control(action: str, item_id: int | None, body: dict[str, Any] | None) -> Any:
        status, data = await backend.control(action, item_id, body)
        return JSONResponse(data, status_code=status)

    @app.post("/api/control/{action}")
    async def control(action: str, body: dict[str, Any] | None = Body(default=None)) -> Any:
        return await _control(action, None, body)

    @app.post("/api/control/{action}/{item_id}")
    async def control_item(
        action: str, item_id: int, body: dict[str, Any] | None = Body(default=None)
    ) -> Any:
        return await _control(action, item_id, body)

    @app.get("/api/reports/{sid}")
    async def report(sid: str) -> dict[str, Any]:
        rep = await backend.report(sid)
        if rep is None:
            raise HTTPException(404, "no report for that session yet")
        return rep

    @app.get("/api/scoreboard")
    async def scoreboard() -> dict[str, Any]:
        return await backend.scoreboard() or {"raiders": []}

    @app.get("/api/sessions/{sid}")
    async def session(sid: str) -> dict[str, Any]:
        detail = await backend.session_detail(sid)
        if detail is None:
            raise HTTPException(404, "unknown session")
        return detail

    @app.get("/api/events/{eid}")
    async def event(eid: int) -> dict[str, Any]:
        msg = await backend.event(eid)
        if msg is None:
            raise HTTPException(404, "unknown event")
        return msg

    return app
