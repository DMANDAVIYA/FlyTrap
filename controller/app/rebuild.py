"""Ask the rebuilder to restart Olympus's servers one at a time (only after Zeus approves)."""

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
                                "message": "Olympus servers restarted one at a time; the site stayed up" if ok
                                else f"Restart failed: {resp.text[:120]}", "evidence": []})
    return ok, "restart complete" if ok else "restart failed"
