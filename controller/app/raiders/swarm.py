"""Red swarm orchestration: release, stop, reset, scoreboard."""

from __future__ import annotations

import asyncio
import logging

from ..bait import demo_password
from ..context import Ctx
from ..llm import LLM
from .llm_raider import run_llm
from .loot import LootBoard
from .personas import BY_NAME, PERSONAS, Persona
from .runner import RunnerClient
from .scripted import run_scripted

log = logging.getLogger("controller.redswarm")


class RedSwarm:
    def __init__(self, ctx: Ctx) -> None:
        self.ctx = ctx
        self.loot = LootBoard()
        self.stop_event = asyncio.Event()
        self.tasks: dict[str, asyncio.Task] = {}
        self.state: dict[str, str] = {}
        self.demo_pw = demo_password(ctx.settings.bait_secret)

    def _slot(self, index: int) -> str:
        slots = self.ctx.settings.raider_slots
        return slots[index % len(slots)]

    async def _emit_thought(self, raider: str, text: str) -> None:
        await self.ctx.db.emit("thought", {"agent": raider, "team": "red", "text": text}, "-")

    async def _roster(self, raider: str, state: str, mode: str) -> None:
        self.state[raider] = state
        await self.ctx.db.emit("roster", {"agent": raider, "team": "red", "state": state, "mode": mode})

    def mode_for(self, persona: Persona, forced: str | None = None) -> str:
        if forced == "scripted" or persona.default_mode != "ai":
            return "scripted"
        return "ai" if LLM(self.ctx.settings.raider_model_for(persona.name)).available else "scripted"

    async def release(self, names: list[str], crowd: int, drones: int, demo: bool, mode: str | None = None) -> dict:
        """Start the crowd and the raiders. Returns at once; raiders launch staggered in the background."""
        self.stop_event.clear()
        self.ctx.state.demo_mode = demo
        chosen = [n for n in names if n in BY_NAME and not (n in self.tasks and not self.tasks[n].done())]
        await self.ctx.db.emit("swarm", {"state": "released", "raiders": chosen, "crowd": crowd, "drones": drones})
        await self._start_crowd(crowd, drones)
        asyncio.create_task(self._launch(chosen, demo, mode))
        return {"started": chosen, "demo": demo}

    async def _launch(self, names: list[str], demo: bool, mode: str | None) -> None:
        gap = 2.0 if demo else 5.0
        for i, name in enumerate(names):
            if self.stop_event.is_set():
                return
            if i:
                await asyncio.sleep(gap)
            self.tasks[name] = asyncio.create_task(self._run_one(BY_NAME[name], i, mode))

    async def _run_one(self, persona: Persona, index: int, forced: str | None) -> None:
        run = RunnerClient(self.ctx.http, self._slot(index))
        await run.reset()
        mode = self.mode_for(persona, forced)
        await self._roster(persona.name, "roaming", mode)
        try:
            if mode == "ai":
                llm = LLM(self.ctx.settings.raider_model_for(persona.name))
                await run_llm(persona, llm, run, self._emit_thought, self.loot, self.demo_pw,
                              self.ctx.settings.raider_max_steps, self.ctx.settings.raider_max_minutes, self.stop_event)
            else:
                await run_scripted(persona.name, run, persona, self._emit_thought, self.ctx.state.demo_mode,
                                   self.loot, self.demo_pw)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("raider %s failed", persona.name)
        finally:
            await self._roster(persona.name, "done", mode)

    async def _start_crowd(self, customers: int, drones: int) -> None:
        if customers <= 0 and drones <= 0:
            return
        try:
            await self.ctx.http.post(f"{self.ctx.settings.crowd_url}/start",
                                     json={"customers": customers, "drones": drones,
                                           "demo": self.ctx.state.demo_mode}, timeout=10.0)
        except Exception as exc:  # noqa: BLE001 - the crowd is optional; never fail a release over it
            log.warning("crowd start failed: %s", exc)

    async def stop(self) -> dict:
        self.stop_event.set()
        for task in self.tasks.values():
            task.cancel()
        self.tasks.clear()
        try:
            await self.ctx.http.post(f"{self.ctx.settings.crowd_url}/stop", timeout=5.0)
        except Exception:  # noqa: BLE001 - crowd may already be down
            pass
        for name in list(self.state):
            await self._roster(name, "idle", self.mode_for(BY_NAME[name]))
        await self.ctx.db.emit("swarm", {"state": "stopped"})
        return {"stopped": True}

    async def reset(self) -> dict:
        await self.stop()
        self.loot.clear()
        await self.ctx.db.clear_fingerprints()
        await self.ctx.db.expire_pending_approvals()
        ok, data = await self.ctx.gw.reset_all()
        await self.ctx.db.emit("swarm", {"state": "reset"})
        return {"reset": ok, **({} if ok else {"error": data.get("error")})}

    def scoreboard(self) -> list[dict]:
        board = []
        for persona in PERSONAS:
            items = [i for i in self.loot.items if i.raider == persona.name]
            board.append({"raider": persona.name, "mode": self.mode_for(persona),
                          "state": self.state.get(persona.name, "idle"),
                          "loot": len(items), "kinds": sorted({i.kind for i in items})})
        return board
