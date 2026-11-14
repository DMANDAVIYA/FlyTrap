"""Ask the rebuilder to recreate Olympus from clean images (only after Zeus approves)."""

from __future__ import annotations

import httpx

from .context import Ctx


async def rebuild_olympus(ctx: Ctx, approval_id: int) -> tuple[bool, str]:
    try:
        resp = await ctx.http.post(f"{ctx.settings.rebuilder_url}/rebuild-real",
                                   json={"approval_id": approval_id},
                                   headers={"X-Admin-Token": ctx.settings.admin_token}, timeout=120.0)
    except httpx.HTTPError as exc:
        return False, f"rebuilder unreachable: {exc}"
    ok = resp.status_code < 300
    await ctx.db.emit("alert", {"agent": "hermes", "severity": "info" if ok else "warn",
                                "message": "Olympus rebuilt from clean images, one server at a time" if ok
                                else f"Rebuild failed: {resp.text[:120]}", "evidence": []})
    return ok, "rebuild complete" if ok else "rebuild failed"
