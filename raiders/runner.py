"""A raider's hands. Sends exactly one request per call, to our gateway only.

The controller holds the raider's brain and API keys; this container has
neither. It can reach only http://gateway:8080 and refuses anything else, so a
compromised or confused raider can do nothing but talk to our own site.
"""

from __future__ import annotations

import os
import time

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

GATEWAY = os.getenv("GATEWAY_URL", "http://gateway:8080")
SLOT = os.getenv("RAIDER_SLOT", "raider")
app = FastAPI(docs_url=None, redoc_url=None)
client = httpx.AsyncClient(base_url=GATEWAY, timeout=30.0, follow_redirects=False)


class Req(BaseModel):
    raider: str = SLOT
    user_agent: str = "research-agent/1.0"
    method: str = "GET"
    path: str = "/"
    headers: dict = {}
    body: str | None = None


def safe(path: str) -> bool:
    return path.startswith("/") and not path.startswith("//") and "://" not in path and "\\" not in path


@app.post("/do")
async def do(req: Req):
    if not safe(req.path):
        return {"status": 0, "headers": {}, "body": "", "ms": 0.0, "error": "path only"}
    headers = {k: v for k, v in req.headers.items() if isinstance(v, str) and k.lower() not in ("host", "x-raider")}
    headers["user-agent"] = req.user_agent
    headers["x-raider"] = req.raider
    if req.body is not None and "content-type" not in {k.lower() for k in headers}:
        headers["content-type"] = "application/x-www-form-urlencoded"
    started = time.perf_counter()
    try:
        resp = await client.request(req.method, req.path, headers=headers, content=req.body)
    except httpx.HTTPError as exc:
        return {"status": 0, "headers": {}, "body": f"error: {exc}", "ms": 0.0}
    ms = (time.perf_counter() - started) * 1000
    return {"status": resp.status_code,
            "headers": {k: v for k, v in resp.headers.items() if k.lower() in ("location", "content-type", "set-cookie")},
            "body": resp.text[:20000], "ms": round(ms, 1)}


@app.post("/reset")
async def reset():
    return {"ok": True}


@app.get("/healthz")
async def healthz():
    return {"ok": True, "slot": SLOT}
