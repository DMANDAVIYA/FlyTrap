"""Controller HTTP API: swarm control, approvals, raiders, reports, health."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Literal

import httpx
from fastapi import FastAPI, Request
from pydantic import BaseModel

from .config import settings
from .context import Ctx, SwarmState
from .db import DB
from .gateway_client import GatewayClient
from .llm import LLM
from .policy import Policy
from .raiders.personas import PERSONAS
from .raiders.swarm import RedSwarm
from .swarm.engine import Engine
from .swarm.report import build_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("controller")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = DB(settings.events_db_url)
    await db.connect()
    http = httpx.AsyncClient()
    ctx = Ctx(settings=settings, db=db, gw=GatewayClient(settings.gateway_admin_url, settings.admin_token),
              http=http, state=SwarmState())
    policy = Policy(ctx)
    engine = Engine(ctx, policy)
    app.state.ctx, app.state.policy, app.state.engine, app.state.red = ctx, policy, engine, RedSwarm(ctx)
    await engine.start()
    log.info("controller ready; blue model=%s, report model=%s",
             engine.models["athena"].label, LLM(settings.report_model).label)
    yield
    await http.aclose()


app = FastAPI(title="flytrap-controller", docs_url=None, redoc_url=None, lifespan=lifespan)


class ReleaseIn(BaseModel):
    raiders: list[str] = [p.name for p in PERSONAS]
    crowd: int = 30
    drones: int = 0
    demo_mode: bool = True


class DecisionIn(BaseModel):
    decision: Literal["approve", "reject"]
    by: str = "zeus"


class ToolIn(BaseModel):
    agent: str = "zeus"
    reason: str = ""
    args: dict = {}


class RaiderIn(BaseModel):
    mode: Literal["ai", "scripted"] | None = None


@app.get("/health")
async def health(request: Request):
    red = request.app.state.red
    return {"ok": True, "blue": request.app.state.engine.health(),
            "red": [{"raider": p.name, "mode": red.mode_for(p), "state": red.state.get(p.name, "idle")}
                    for p in PERSONAS]}


@app.post("/swarm/release")
async def release(body: ReleaseIn, request: Request):
    return await request.app.state.red.release(body.raiders, body.crowd, body.drones, body.demo_mode)


@app.post("/swarm/stop")
async def stop(request: Request):
    return await request.app.state.red.stop()


@app.post("/swarm/reset")
async def reset(request: Request):
    request.app.state.engine.reset()
    return await request.app.state.red.reset()


@app.post("/raiders/{name}/start")
async def start_raider(name: str, body: RaiderIn, request: Request):
    red = request.app.state.red
    return await red.release([name], crowd=0, drones=0, demo=request.app.state.ctx.state.demo_mode, mode=body.mode)


@app.get("/scoreboard")
async def scoreboard(request: Request):
    return {"scoreboard": request.app.state.red.scoreboard()}


@app.post("/tools/{name}")
async def run_tool(name: str, body: ToolIn, request: Request):
    return (await request.app.state.policy.execute(body.agent, name, body.args, body.reason)).dict()


@app.get("/approvals")
async def approvals(request: Request):
    return {"approvals": await request.app.state.ctx.db.pending_approvals()}


@app.post("/approvals/{approval_id}")
async def decide(approval_id: int, body: DecisionIn, request: Request):
    return (await request.app.state.policy.decide(approval_id, body.decision, body.by)).dict()


@app.post("/reports/{sid}")
async def report(sid: str, request: Request):
    return {"ok": await build_report(request.app.state.ctx, sid)}
