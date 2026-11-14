"""Admin API on the control network only (bound to the gateway's control address).

Every route goes through `Gateway`, which enforces the hard rules.
"""

from __future__ import annotations

import hmac
import time

import httpx
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .canaries import Canary
from .core import Gateway, RuleError
from .rules import DynamicRule

PACES = {"normal", "slow", "drip", "freeze"}
LABELS = {"unknown", "human", "scanner", "ai_agent"}
LADDER = {"watch", "engage", "contain", "eject"}


class RouteIn(BaseModel):
    side: str
    reason: str = ""
    approval_id: int | None = None


class PaceIn(BaseModel):
    mode: str
    rate: int | None = None


class ReasonIn(BaseModel):
    reason: str = ""


class LabelIn(BaseModel):
    label: str
    confidence: float | None = None
    reasons: list[str] | None = None


class MetaIn(BaseModel):
    ladder: str | None = None


class LockdownIn(BaseModel):
    state: str
    by: str
    reason: str = ""


class RuleIn(BaseModel):
    id: str
    path_prefix: str | None = None
    path_regex: str | None = None
    ua_contains: str | None = None
    action: str = "flip"
    score: int = 30
    ttl_min: int = 60
    session_id: str | None = None
    approval_id: int | None = None


class PlantIn(BaseModel):
    session_id: str
    kind: str
    value: str
    where: str = "account"


class RotateIn(BaseModel):
    user_id: int
    reason: str = ""


class UpstreamIn(BaseModel):
    enabled: bool


def build_admin(gw: Gateway) -> FastAPI:
    def auth(x_admin_token: str = Header(default="")) -> None:
        if not gw.settings.admin_token or not hmac.compare_digest(x_admin_token, gw.settings.admin_token):
            raise HTTPException(status_code=401, detail="bad admin token")

    app = FastAPI(title="charon-admin", docs_url=None, redoc_url=None)
    r = APIRouter(prefix="/_admin", dependencies=[Depends(auth)])

    @app.exception_handler(RuleError)
    async def rule_error(_, exc: RuleError):
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=409)

    def session_or_404(sid: str):
        s = gw.store.get(sid)
        if not s:
            raise HTTPException(status_code=404, detail="no such session")
        return s

    @r.get("/health")
    async def health():
        return {"ok": True, "pods": gw.pods.snapshot(), "lockdown": gw.lockdown.state,
                "sessions": len(gw.store.active()), "dropped_events": gw.writer.dropped,
                "upstreams": sorted(gw.enabled_upstreams)}

    @r.get("/sessions")
    async def sessions():
        return {"ok": True, "sessions": [s.public() for s in gw.store.active()]}

    @r.get("/sessions/{sid}")
    async def session(sid: str):
        return {"ok": True, "session": session_or_404(sid).public()}

    @r.post("/sessions/{sid}/route")
    async def route(sid: str, body: RouteIn):
        await gw.route(session_or_404(sid), body.side, body.reason, body.approval_id)
        return {"ok": True}

    @r.post("/sessions/{sid}/pace")
    async def pace(sid: str, body: PaceIn):
        s = session_or_404(sid)
        if body.mode not in PACES:
            raise HTTPException(400, "unknown pace")
        if not s.trapped:
            raise RuleError("pacing applies to trapped sessions only")
        s.pace, s.pace_count = body.mode, 0
        if body.rate:
            s.drip_rate = max(1, min(body.rate, 100))
        gw.store.touch(s)
        return {"ok": True}

    @r.post("/sessions/{sid}/block")
    async def block(sid: str, body: ReasonIn):
        gw.block(session_or_404(sid))
        return {"ok": True}

    @r.post("/sessions/{sid}/label")
    async def label(sid: str, body: LabelIn):
        s = session_or_404(sid)
        if body.label not in LABELS:
            raise HTTPException(400, "unknown label")
        s.label, s.confidence, s.reasons = body.label, body.confidence, body.reasons
        gw.store.touch(s)
        return {"ok": True}

    @r.post("/sessions/{sid}/meta")
    async def meta(sid: str, body: MetaIn):
        s = session_or_404(sid)
        if body.ladder:
            if body.ladder not in LADDER:
                raise HTTPException(400, "unknown ladder step")
            s.ladder = body.ladder
        gw.store.touch(s)
        return {"ok": True}

    @r.post("/lockdown")
    async def lockdown(body: LockdownIn):
        ok, msg = gw.lockdown.request(body.state, body.by, body.reason)
        if not ok:
            raise RuleError(msg)
        return {"ok": True, "state": gw.lockdown.state}

    @r.post("/rules")
    async def add_rule(body: RuleIn):
        if body.session_id is None and (body.approval_id is None or
                                        not await gw.writer.approval_ok(body.approval_id, "new_rule")
                                        and not await gw.writer.approval_ok(body.approval_id, "virtual_patch")):
            raise RuleError("rules for everyone need a Zeus approval")
        gw.rules.append(DynamicRule(body.id, body.path_prefix, body.path_regex, body.ua_contains, body.action,
                                    body.score, body.session_id, time.time() + body.ttl_min * 60))
        return {"ok": True, "rules": len(gw.rules)}

    @r.post("/pods/{pod}/plant")
    async def plant(pod: str, body: PlantIn):
        if pod not in gw.pods.pods:
            raise HTTPException(404, "no such pod")
        s = gw.store.get(body.session_id)
        if not s or s.pod != pod or not s.trapped:
            raise RuleError("bait is planted only for trapped sessions in their own pod")
        try:
            resp = await gw.client.post(f"http://{pod}:{gw.settings.upstream_port}/_edge/plant", json=body.model_dump())
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"pod unreachable: {exc}") from exc
        if resp.status_code >= 300:
            raise HTTPException(502, f"pod refused plant: {resp.status_code}")
        gw.register_canary(Canary(body.value, body.kind, body.session_id, f"{pod}:{body.where}"))
        return {"ok": True}

    @r.post("/pods/{pod}/reset")
    async def reset_pod(pod: str):
        if pod not in gw.pods.pods:
            raise HTTPException(404, "no such pod")
        if gw.pods.pods[pod].sessions:
            raise RuleError("pod still has live sessions")
        return {"ok": await gw.reset_pod(pod)}

    @r.post("/reset")
    async def reset_all():
        return {"ok": True, "ended_sessions": await gw.reset_all()}

    @r.post("/rotate")
    async def rotate(body: RotateIn):
        upstream = gw.real_upstream()
        try:
            resp = await gw.client.post(f"http://{upstream}:{gw.settings.upstream_port}/_edge/rotate",
                                        json={"user_id": body.user_id})
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"real side unreachable: {exc}") from exc
        return {"ok": resp.status_code < 300, "status": resp.status_code}

    @r.post("/upstreams/{name}")
    async def upstream(name: str, body: UpstreamIn):
        if name not in gw.settings.real_upstreams:
            raise HTTPException(404, "no such upstream")
        if body.enabled:
            gw.enabled_upstreams.add(name)
        elif len(gw.enabled_upstreams - {name}) == 0:
            raise RuleError("at least one real upstream must stay in rotation")
        else:
            gw.enabled_upstreams.discard(name)
        return {"ok": True, "upstreams": sorted(gw.enabled_upstreams)}

    app.include_router(r)
    return app
