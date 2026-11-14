"""The policy guard: who may call which tool, under what conditions.

Every call (allowed, rejected or waiting for Zeus) becomes an `actions` row
and an `action` event, so the dashboard shows the guard working.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass

from .context import Ctx
from .tools import TOOLS

ALLOWLIST: dict[str, set[str]] = {
    "athena": {"request_lockdown", "request_release", "request_rebuild", "virtual_patch", "link_campaign", "post_note"},
    "argus": {"label_session", "quarantine", "post_note"},
    "hephaestus": {"plant_bait", "rotate_keys", "post_note"},
    "cerberus": {"set_pace", "block", "post_note"},
    "mnemosyne": {"save_fingerprint", "suggest_rule", "post_note"},
    "clio": {"write_report", "post_note"},
    "hermes": {"alert", "post_note"},
    "zeus": set(TOOLS),  # the human; buttons on the dashboard
}
QUIET_TOOLS = {"post_note", "alert", "write_report"}  # logged through their own events
SWARM_PER_MIN, AGENT_SESSION_PER_MIN = 20, 3


@dataclass
class Result:
    ok: bool
    status: str
    message: str
    action_id: int | None = None
    approval_id: int | None = None

    def dict(self) -> dict:
        return self.__dict__.copy()


class Policy:
    def __init__(self, ctx: Ctx) -> None:
        self.ctx = ctx
        self.swarm_calls: deque[float] = deque()
        self.per_target: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def _rate_ok(self, actor: str, session: str) -> bool:
        if actor == "zeus":
            return True
        now = time.time()
        for q in (self.swarm_calls, self.per_target[(actor, session)]):
            while q and now - q[0] > 60:
                q.popleft()
        if len(self.swarm_calls) >= SWARM_PER_MIN or len(self.per_target[(actor, session)]) >= AGENT_SESSION_PER_MIN:
            return False
        self.swarm_calls.append(now)
        self.per_target[(actor, session)].append(now)
        return True

    async def execute(self, actor: str, name: str, args: dict, reason: str = "", evidence: list[int] | None = None) -> Result:
        evidence = [int(e) for e in (evidence or args.get("evidence") or []) if str(e).isdigit()]
        args = {**args, "_actor": actor}
        session = args.get("session") or "-"
        tool = TOOLS.get(name)
        if tool is None:
            return await self._log(actor, name, args, reason, evidence, "rejected", f"unknown tool {name}")
        if name not in ALLOWLIST.get(actor, set()):
            return await self._log(actor, name, args, reason, evidence, "rejected", f"{actor} does not hold {name}")
        missing = [k for k in tool.required if k not in args or args[k] in (None, "", [])]
        if missing:
            return await self._log(actor, name, args, reason, evidence, "rejected", f"missing {', '.join(missing)}")
        if tool.guard:
            ok, why = await tool.guard(self.ctx, args)
            if not ok:
                return await self._log(actor, name, args, reason, evidence, "rejected", why)
        if not self._rate_ok(actor, session):
            return await self._log(actor, name, args, reason, evidence, "rejected", "rate limit")
        needs_zeus = bool(tool.approval_kind) and tool.approval_if(args) and actor != "zeus"
        if needs_zeus:
            return await self._ask_zeus(actor, tool.approval_kind, args, reason, evidence)
        ok, message = await tool.impl(self.ctx, args)
        status = "done" if ok else "failed"
        if name in QUIET_TOOLS and ok:
            return Result(True, status, message)
        return await self._log(actor, name, args, reason, evidence, status, message)

    async def _log(self, actor: str, name: str, args: dict, reason: str, evidence: list[int], status: str,
                   message: str) -> Result:
        clean = {k: v for k, v in args.items() if not k.startswith("_") and k != "evidence"}
        session = args.get("session")
        action_id = await self.ctx.db.insert_action(actor, name, session, clean, reason or message, evidence, status)
        await self.ctx.db.emit("action", {"id": action_id, "actor": actor, "tool": name, "args": clean,
                                          "reason": reason or message, "status": status, "result": message,
                                          "evidence": evidence}, session or "-")
        return Result(status in ("done", "pending_approval"), status, message, action_id)

    async def _ask_zeus(self, actor: str, kind: str, args: dict, reason: str, evidence: list[int]) -> Result:
        clean = {k: v for k, v in args.items() if not k.startswith("_")}
        tool = {"new_rule": "suggest_rule", "virtual_patch": "virtual_patch", "release": "request_release",
                "rebuild": "request_rebuild"}[kind]
        result = await self._log(actor, tool, args, reason, evidence, "pending_approval", "waiting for Zeus")
        summary = reason or f"{actor} asks to {tool.replace('_', ' ')}"
        approval_id = await self.ctx.db.insert_approval(kind, summary, {**clean, "tool": tool, "actor": actor}, result.action_id)
        await self.ctx.db.emit("approval", {"id": approval_id, "kind": kind, "summary": summary, "status": "pending",
                                            "actor": actor}, args.get("session") or "-")
        result.approval_id = approval_id
        return result

    async def decide(self, approval_id: int, decision: str, by: str = "zeus") -> Result:
        approval = await self.ctx.db.get_approval(approval_id)
        if not approval or approval["status"] != "pending":
            return Result(False, "rejected", "no such pending approval")
        status = "approved" if decision == "approve" else "rejected"
        await self.ctx.db.decide_approval(approval_id, status, by)
        await self.ctx.db.emit("approval", {"id": approval_id, "kind": approval["kind"], "summary": approval["summary"],
                                            "status": status, "by": by}, approval["payload"].get("session") or "-")
        if approval["action_id"]:
            await self.ctx.db.set_action_status(approval["action_id"], status)
        if status != "approved":
            return Result(True, status, "rejected by Zeus")
        payload = approval["payload"]
        tool = TOOLS[payload["tool"]]
        ok, message = await tool.impl(self.ctx, {**payload, "approval_id": approval_id})
        await self._log("zeus", tool.name, {**payload, "approval_id": approval_id}, f"approved by Zeus: {approval['summary']}",
                        [], "done" if ok else "failed", message)
        return Result(ok, "done" if ok else "failed", message)
