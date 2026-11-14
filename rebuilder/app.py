"""Restart the real servers one at a time, keeping the site up.

The only container with the Docker socket. It does exactly one fixed thing,
only on the control network, and only when called with the admin token. No
model can reach it.
"""

from __future__ import annotations

import hmac
import os

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
PROJECT = os.getenv("COMPOSE_PROJECT", "flytrap")
TARGETS = [t.strip() for t in os.getenv("TARGETS", "web-1,web-2").split(",") if t.strip()]
GATEWAY_ADMIN = os.getenv("GATEWAY_ADMIN_URL", "http://gateway-admin:8081")
app = FastAPI(docs_url=None, redoc_url=None)


class RebuildIn(BaseModel):
    approval_id: int | None = None


def _docker():
    import docker
    return docker.from_env()


async def _upstream(name: str, enabled: bool) -> None:
    async with httpx.AsyncClient(timeout=10.0) as c:
        try:
            await c.post(f"{GATEWAY_ADMIN}/_admin/upstreams/{name}", json={"enabled": enabled},
                         headers={"X-Admin-Token": ADMIN_TOKEN})
        except httpx.HTTPError:
            pass


@app.post("/rebuild-real")
async def rebuild_real(body: RebuildIn, x_admin_token: str = Header(default="")):
    if not ADMIN_TOKEN or not hmac.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="bad admin token")
    client = _docker()
    done = []
    for name in TARGETS:  # roll one at a time so the site stays up
        await _upstream(name, False)
        matches = client.containers.list(all=True, filters={"label": [f"com.docker.compose.project={PROJECT}",
                                                                      f"com.docker.compose.service={name}"]})
        for container in matches:
            container.restart(timeout=10)
        await _upstream(name, True)
        done.append(name)
    return {"ok": True, "rebuilt": done}


@app.get("/healthz")
async def healthz():
    return {"ok": True, "targets": TARGETS}
