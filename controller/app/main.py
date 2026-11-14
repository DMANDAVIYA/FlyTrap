"""Controller HTTP API: swarm control, approvals, raiders, reports, health."""

from __future__ import annotations

import logging

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from .config import settings
from .context import Ctx, SwarmState
from .db import DB
from .gateway_client import GatewayClient
from .policy import Policy
from .raiders.personas import PERSONAS
from .raiders.swarm import RedSwarm
from .swarm.engine import Engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("controller")

app = FastAPI(title="flytrap-controller", docs_url=None, redoc_url=None)


class ReleaseIn(BaseModel):
    raiders: list[str] = [p.name for p in PERSONAS]
    crowd: int = 30
    drones: int = 0
    demo_mode: bool = True


class DecisionIn(BaseModel):
    decision: str
    by: str = "zeus"


class ToolIn(BaseModel):
    agent: str = "zeus"
    reason: str = ""
    args: dict = {}


class RaiderIn(BaseModel):
    mode: str | None = None


@app.on_event("startup")
async def startup() -> None:
    db = DB(settings.events_db_url)
    await db.connect()
    http = httpx.AsyncClient()
    gw = GatewayClient(settings.gateway_admin_url, settings.admin_token)
    ctx = Ctx(settings=settings, db=db, gw=gw, http=http, state=SwarmState())
    app.state.ctx = ctx
    app.state.policy = Policy(ctx)
    app.state.engine = Engine(ctx, app.state.policy)
    app.state.red = RedSwarm(ctx)
    await app.state.engine.start()
    log.info("controller ready; blue model=%s report model=%s",
             app.state.engine.models["athena"].label, settings.report_model or "rules")


@app.get("/health")
async def health():
    return {"ok": True, "blue": app.state.engine.health(),
            "red": [{"raider": p.name, "mode": app.state.red.mode_for(p),
                     "state": app.state.red.state.get(p.name, "idle")} for p in PERSONAS]}


@app.post("/swarm/release")
async def release(body: ReleaseIn):
    return await app.state.red.release(body.raiders, body.crowd, body.drones, body.demo_mode)


@app.post("/swarm/stop")
async def stop():
    return await app.state.red.stop()


@app.post("/swarm/reset")
async def reset():
    app.state.engine.reset()
    return await app.state.red.reset()


@app.post("/raiders/{name}/start")
async def start_raider(name: str, body: RaiderIn):
    return await app.state.red.release([name], crowd=0, drones=0, demo=app.state.ctx.state.demo_mode)


@app.get("/scoreboard")
async def scoreboard():
    return {"scoreboard": app.state.red.scoreboard()}


@app.post("/tools/{name}")
async def run_tool(name: str, body: ToolIn):
    result = await app.state.policy.execute(body.agent, name, body.args, body.reason)
    return result.dict()


@app.get("/approvals")
async def approvals():
    return {"approvals": await app.state.ctx.db.pending_approvals()}


@app.post("/approvals/{approval_id}")
async def decide(approval_id: int, body: DecisionIn):
    return (await app.state.policy.decide(approval_id, body.decision, body.by)).dict()


@app.post("/reports/{sid}")
async def report(sid: str):
    from .swarm.report import build_report
    ok = await build_report(app.state.ctx, sid)
    return {"ok": ok}
