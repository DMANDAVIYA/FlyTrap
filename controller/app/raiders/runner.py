"""Client for a raider's runner container: one request at a time, gateway only."""

from __future__ import annotations

from dataclasses import dataclass

import httpx


class ScopeError(Exception):
    """A raider asked for anything other than a path on our own site."""


@dataclass
class Page:
    status: int
    headers: dict
    body: str
    ms: float


def check_path(path: str) -> str:
    """Raiders may only send a path; never a scheme, host or protocol-relative URL."""
    path = (path or "/").strip()
    if not path.startswith("/") or path.startswith("//") or "://" in path or "\\" in path:
        raise ScopeError(f"only paths on this site are allowed, got {path[:60]!r}")
    return path


class RunnerClient:
    def __init__(self, http: httpx.AsyncClient, slot: str) -> None:
        self.http, self.base = http, f"http://{slot}:8060"

    async def do(self, raider: str, ua: str, method: str, path: str, headers: dict | None = None,
                 body: str | None = None) -> Page:
        payload = {"raider": raider, "user_agent": ua, "method": method.upper(), "path": check_path(path),
                   "headers": {k: v for k, v in (headers or {}).items() if isinstance(v, str)}, "body": body}
        resp = await self.http.post(f"{self.base}/do", json=payload, timeout=60.0)
        resp.raise_for_status()
        data = resp.json()
        return Page(data["status"], data.get("headers", {}), data.get("body", ""), data.get("ms", 0.0))

    async def reset(self) -> None:
        try:
            await self.http.post(f"{self.base}/reset", timeout=5.0)
        except httpx.HTTPError:
            pass
