"""Proxy dashboard buttons to the controller (CONTROLLER_URL, contract 6.6)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger("dash.control")

RAIDERS = ["prometheus", "pandora", "odysseus", "icarus", "sisyphus"]
DEFAULT_RELEASE = {"raiders": RAIDERS, "crowd": 30, "drones": 0, "demo_mode": True}

# action -> (method, controller path, default body). "{id}" is filled from the URL.
ROUTES: dict[str, tuple[str, str, dict[str, Any]]] = {
    "release": ("POST", "/swarm/release", DEFAULT_RELEASE),
    "stop": ("POST", "/swarm/stop", {}),
    "reset": ("POST", "/swarm/reset", {}),
    "lockdown": (
        "POST",
        "/tools/request_lockdown",
        {"agent": "zeus", "reason": "Manual lockdown from the Dolos console"},
    ),
    # Not in contract 6.6 yet: the controller should expose this tool for zeus.
    "cancel_lockdown": (
        "POST",
        "/tools/cancel_lockdown",
        {"agent": "zeus", "reason": "Cancelled by Zeus from the Dolos console"},
    ),
    "approve": ("POST", "/approvals/{id}", {"decision": "approve", "by": "human"}),
    "reject": ("POST", "/approvals/{id}", {"decision": "reject", "by": "human"}),
}
NEEDS_ID = {"approve", "reject"}
SLOW = {"approve": 130.0, "reset": 30.0}  # approving a rebuild rolls both real servers; a reset clears every pod


def resolve(action: str, item_id: int | None) -> tuple[str, str, dict[str, Any]] | None:
    route = ROUTES.get(action)
    if route is None or (action in NEEDS_ID and item_id is None):
        return None
    method, path, body = route
    return method, path.replace("{id}", str(item_id)), dict(body)


class ControllerProxy:
    def __init__(self, base_url: str) -> None:
        self.base = base_url.rstrip("/")
        self.http = httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=3.0))

    async def call(
        self, action: str, item_id: int | None, body: dict[str, Any] | None
    ) -> tuple[int, dict[str, Any]]:
        route = resolve(action, item_id)
        if route is None:
            return 404, {"ok": False, "error": f"unknown action: {action}"}
        method, path, default = route
        payload = {**default, **(body or {})}
        try:
            r = await self.http.request(method, self.base + path, json=payload,
                                        timeout=httpx.Timeout(SLOW.get(action, 8.0), connect=3.0))
        except httpx.HTTPError as exc:
            log.warning("controller %s %s failed: %s", method, path, exc)
            return 502, {"ok": False, "error": f"controller unreachable ({exc.__class__.__name__})"}
        try:
            data: Any = r.json()
        except ValueError:
            data = {"text": r.text[:500]}
        if not isinstance(data, dict):
            data = {"result": data}
        data.setdefault("ok", r.is_success)
        return r.status_code, data

    async def scoreboard(self) -> Any | None:
        try:
            r = await self.http.get(self.base + "/scoreboard")
            r.raise_for_status()
            return normalize_scoreboard(r.json())
        except (httpx.HTTPError, ValueError):
            return None

    async def aclose(self) -> None:
        await self.http.aclose()


def normalize_scoreboard(raw: Any) -> dict[str, Any]:
    """Always {"raiders": [...]} so the dashboard has one shape to render."""
    if isinstance(raw, list):
        return {"raiders": raw}
    if isinstance(raw, dict):
        if isinstance(raw.get("raiders"), list):
            return raw
        rows = [{"raider": k, **v} for k, v in raw.items() if isinstance(v, dict)]
        if rows:
            return {"raiders": rows}
    return {"raiders": [], "raw": raw}
