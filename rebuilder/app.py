"""Restart the real servers one at a time, keeping the site up.

The only container with the Docker socket. It does exactly one fixed thing,
only on the control network, and only when called with the admin token. No
model can reach it.
"""

from __future__ import annotations

import asyncio
import hmac
import os

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
PROJECT = os.getenv("COMPOSE_PROJECT", "flytrap")
TARGETS = [t.strip() for t in os.getenv("TARGETS", "web-1,web-2").split(",") if t.strip()]
GATEWAY_ADMIN = os.getenv("GATEWAY_ADMIN_URL", "http://gateway-admin:8081")
DRAIN_S = 1.0  # let requests already on a server finish before restarting it
app = FastAPI(docs_url=None, redoc_url=None)


class RebuildIn(BaseModel):
    approval_id: int | None = None


def _docker():
    import docker
    return docker.from_env()


async def _upstream(name: str, enabled: bool) -> bool:
    """Take a server out of rotation, or put it back (the gateway waits until it answers)."""
    async with httpx.AsyncClient(timeout=40.0) as c:
        try:
            resp = await c.post(f"{GATEWAY_ADMIN}/_admin/upstreams/{name}", json={"enabled": enabled},
                                headers={"X-Admin-Token": ADMIN_TOKEN})
            return resp.status_code < 300
        except httpx.HTTPError:
            return False


@app.post("/rebuild-real")
async def rebuild_real(body: RebuildIn, x_admin_token: str = Header(default="")):
    if not ADMIN_TOKEN or not hmac.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="bad admin token")
    client = _docker()
    done = []
    for name in TARGETS:  # roll one at a time so the site stays up
        if not await _upstream(name, False):
            raise HTTPException(status_code=503, detail=f"could not take {name} out of rotation; nothing restarted")
        await asyncio.sleep(DRAIN_S)
        matches = client.containers.list(all=True, filters={"label": [f"com.docker.compose.project={PROJECT}",
                                                                      f"com.docker.compose.service={name}"]})
        for container in matches:
            await asyncio.to_thread(container.restart, timeout=10)
        if not await _upstream(name, True):
            raise HTTPException(status_code=503, detail=f"{name} did not come back; stopped before the next server")
        done.append(name)
    return {"ok": True, "rebuilt": done}


@app.get("/healthz")
async def healthz():
    return {"ok": True, "targets": TARGETS}
