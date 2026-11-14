"""Thin client for Charon's admin API. Errors come back as (ok, message)."""

from __future__ import annotations

import httpx


class GatewayClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.client = httpx.AsyncClient(base_url=base_url, headers={"X-Admin-Token": token}, timeout=10.0)

    async def _call(self, method: str, path: str, body: dict | None = None) -> tuple[bool, dict]:
        try:
            resp = await self.client.request(method, f"/_admin{path}", json=body)
        except httpx.HTTPError as exc:
            return False, {"error": f"gateway unreachable: {exc}"}
        try:
            data = resp.json()
        except ValueError:
            data = {"error": resp.text[:200]}
        if resp.status_code >= 300:
            return False, {"error": data.get("error") or data.get("detail") or f"HTTP {resp.status_code}"}
        return True, data

    async def health(self):
        return await self._call("GET", "/health")

    async def sessions(self):
        return await self._call("GET", "/sessions")

    async def label(self, sid: str, label: str, confidence: float, reasons: list[str]):
        return await self._call("POST", f"/sessions/{sid}/label", {"label": label, "confidence": confidence, "reasons": reasons})

    async def route(self, sid: str, side: str, reason: str, approval_id: int | None = None):
        return await self._call("POST", f"/sessions/{sid}/route", {"side": side, "reason": reason, "approval_id": approval_id})

    async def pace(self, sid: str, mode: str, rate: int | None = None):
        return await self._call("POST", f"/sessions/{sid}/pace", {"mode": mode, "rate": rate})

    async def block(self, sid: str, reason: str):
        return await self._call("POST", f"/sessions/{sid}/block", {"reason": reason})

    async def meta(self, sid: str, ladder: str):
        return await self._call("POST", f"/sessions/{sid}/meta", {"ladder": ladder})

    async def lockdown(self, state: str, by: str, reason: str):
        return await self._call("POST", "/lockdown", {"state": state, "by": by, "reason": reason})

    async def add_rule(self, rule: dict):
        return await self._call("POST", "/rules", rule)

    async def plant(self, pod: str, sid: str, kind: str, value: str, where: str):
        return await self._call("POST", f"/pods/{pod}/plant", {"session_id": sid, "kind": kind, "value": value, "where": where})

    async def rotate(self, user_id: int, reason: str):
        return await self._call("POST", "/rotate", {"user_id": user_id, "reason": reason})

    async def reset_all(self):
        return await self._call("POST", "/reset")
