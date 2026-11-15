"""The swarm engine: one loop, seven roles, each woken by its own trigger.

Roles never block each other or the gateway. A role in AI mode falls back to
rules mode for that turn if its model fails, and the dashboard shows which.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

from ..context import Ctx
from ..llm import LLM, LLMError
from ..models import chain
from ..policy import Policy
from ..summaries import active_summaries
from .roles import ROLES, Role, ai_plan, rules_plan

log = logging.getLogger("controller.swarm")
WATCHED = ("flip", "canary", "tripwire", "lockdown", "approval", "report", "campaign")


class Engine:
    def __init__(self, ctx: Ctx, policy: Policy) -> None:
        self.ctx, self.policy = ctx, policy
        self.models = {r.name: LLM(chain(r.base) if r.uses_ai else "") for r in ROLES}
        self.running: dict[str, asyncio.Task] = {}
        self.last_run: dict[str, float] = {r.name: 0.0 for r in ROLES}
        self.pending: dict[str, list] = {r.name: [] for r in ROLES}
        self.roster: dict[str, tuple] = {}
        self.last_event = 0
        self.sessions: list[dict] = []

    def mode(self, role: Role) -> str:
        return "ai" if self.models[role.name].available else "rules"

    async def start(self) -> None:
        self.last_event = await self.ctx.db.max_event_id()
        for role in ROLES:
            await self.set_roster(role, "idle")
        asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        last_summary = 0.0
        while True:
            await asyncio.sleep(1)
            try:
                events = await self.ctx.db.events_since(self.last_event, WATCHED)
                if events:
                    self.last_event = events[-1]["id"]
                    parsed = [{**dict(e), "payload": json.loads(e["payload"]) if e["payload"] else {}} for e in events]
                    for queue in self.pending.values():
                        queue.extend(parsed)
                now = time.time()
                if now - last_summary >= self.ctx.settings.blue_interval_s or events:
                    self.sessions = await active_summaries(self.ctx.db)
                    self.ctx.state.summaries.update({s["session"]: s for s in self.sessions})
                    last_summary = now
                for role in ROLES:
                    self._maybe_wake(role, now)
            except Exception:
                log.exception("swarm tick failed")

    def _maybe_wake(self, role: Role, now: float) -> None:
        task = self.running.get(role.name)
        if task and not task.done():
            return
        if now - self.last_run[role.name] < role.interval_s:
            return
        events, self.pending[role.name] = self.pending[role.name], []
        sessions = [s for s in self.sessions if role.covers(s)]
        if role.scope:  # a pod guard only hears about its own visitors
            mine = {s["session"] for s in sessions}
            events = [e for e in events if e.get("session_id") in mine]
        if not sessions and not events:
            return
        self.last_run[role.name] = now
        self.running[role.name] = asyncio.create_task(self._turn(role, sessions, events))

    async def _turn(self, role: Role, sessions: list[dict], events: list) -> None:
        """One role turn. Any failure is logged and the role goes back to idle; the loop never dies."""
        try:
            await self._decide_and_act(role, sessions, events)
        except Exception:
            log.exception("%s turn failed", role.name)
            await self.set_roster(role, "idle")

    async def _decide_and_act(self, role: Role, sessions: list[dict], events: list) -> None:
        plan = rules_plan(self.ctx, role, sessions, events)
        llm = self.models[role.name]
        if plan.empty:
            return
        mode = "rules"
        if llm.available:
            await self.set_roster(role, "thinking", mode="ai")
            targets = [s for s in sessions if any(i.args.get("session") == s["session"] for i in plan.intents)] or sessions[:4]
            try:
                ai = await ai_plan(self.ctx, role, llm, targets, events)
                if not ai.intents:  # the model only talked: keep its words, keep the safe default actions
                    ai.intents, ai.notes = plan.intents, plan.notes
                plan, mode = ai, "ai"
            except LLMError as exc:
                log.warning("%s fell back to rules mode: %s", role.name, exc)
        for session, text in plan.thoughts:
            await self.ctx.db.emit("thought", {"agent": role.name, "team": "blue", "text": text, "mode": mode,
                                               "model": plan.model}, session)
        for intent in plan.intents:
            target = intent.args.get("session")
            await self.set_roster(role, "acting", session=target, mode=mode)
            await self.policy.execute(role.name, intent.tool, intent.args, intent.reason, intent.evidence)
        for session, text, evidence in plan.notes:
            await self.policy.execute(role.name, "post_note", {"session": session if session != "-" else None,
                                                               "note": text, "evidence": evidence}, text, evidence)
        await self.set_roster(role, "idle", mode=mode)

    async def set_roster(self, role: Role, state: str, session: str | None = None, mode: str | None = None) -> None:
        mode = mode or self.mode(role)
        key = (state, session, mode)
        if self.roster.get(role.name) == key:
            return
        self.roster[role.name] = key
        await self.ctx.db.emit("roster", {"agent": role.name, "team": "blue", "state": state, "mode": mode,
                                          "model": self.models[role.name].label, "session": session,
                                          "title": role.title, "persona": role.base, "scope": role.scope})

    def health(self) -> list[dict]:
        return [{"agent": r.name, "title": r.title, "mode": self.mode(r),
                 "state": (self.roster.get(r.name) or ("idle",))[0]} for r in ROLES]

    def reset(self) -> None:
        self.ctx.state.clear()
        for queue in self.pending.values():
            queue.clear()
