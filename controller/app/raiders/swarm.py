"""Red swarm orchestration: release, stop, reset, scoreboard."""

from __future__ import annotations

import asyncio
import logging

from ..bait import demo_password
from ..context import Ctx
from ..llm import LLM
from ..models import chain
from .llm_raider import run_llm
from .loot import LootBoard
from .personas import BY_NAME, INDEX, MAX_COPIES, PERSONAS, Persona, copy_number, copy_of, persona_for
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

    async def _emit_thought(self, raider: str, text: str, model: str = "") -> None:
        payload = {"agent": raider, "persona": raider.partition("-")[0], "team": "red", "text": text}
        if model:
            payload["model"] = model  # which model in the chain actually answered
        await self.ctx.db.emit("thought", payload, "-")

    async def _roster(self, raider: str, state: str, mode: str) -> None:
        self.state[raider] = state
        base = raider.partition("-")[0]
        model = LLM(chain(base)).label if mode == "ai" else "scripted"
        await self.ctx.db.emit("roster", {"agent": raider, "persona": base, "copy": copy_number(raider), "team": "red",
                                          "state": state, "mode": mode, "model": model})

    def mode_for(self, persona: Persona, forced: str | None = None) -> str:
        if forced == "scripted" or persona.default_mode != "ai":
            return "scripted"
        return "ai" if LLM(chain(persona.base)).available else "scripted"

    async def release(self, names: list[str], crowd: int, drones: int, demo: bool, mode: str | None = None,
                      copies: int | None = None) -> dict:
        """Start the crowd and `copies` of each raider. Returns at once; raiders launch staggered in the background."""
        self.stop_event.clear()
        self.ctx.state.demo_mode = demo
        copies = max(1, min(MAX_COPIES, copies or self.ctx.settings.raider_copies))
        squad = [copy_of(BY_NAME[n], k) for k in range(1, copies + 1) for n in names if n in BY_NAME]
        squad = [p for p in squad if not (p.name in self.tasks and not self.tasks[p.name].done())]
        await self.ctx.db.emit("swarm", {"state": "released", "raiders": [p.name for p in squad], "copies": copies,
                                         "crowd": crowd, "drones": drones})
        await self._start_crowd(crowd, drones)
        asyncio.create_task(self._launch(squad, demo, mode))
        return {"started": [p.name for p in squad], "copies": copies, "demo": demo}

    def _slot_for(self, persona: Persona) -> str:
        """Copies of one persona land on different runner slots, so each copy has its own IP."""
        return self._slot(INDEX[persona.base] + copy_number(persona.name) - 1)

    async def _launch(self, squad: list[Persona], demo: bool, mode: str | None) -> None:
        gap = 1.0 if demo else 2.0
        for i, persona in enumerate(squad):
            if self.stop_event.is_set():
                return
            if i:
                await asyncio.sleep(gap)
            self.tasks[persona.name] = asyncio.create_task(self._run_one(persona, mode))

    async def _run_one(self, persona: Persona, forced: str | None) -> None:
        run = RunnerClient(self.ctx.http, self._slot_for(persona))
        await run.reset(persona.name)
        mode = self.mode_for(persona, forced)
        await self._roster(persona.name, "roaming", mode)
        try:
            if mode == "ai":
                llm = LLM(chain(persona.base))
                await run_llm(persona, llm, run, self._emit_thought, self.loot, self.demo_pw,
                              self.ctx.settings.raider_max_steps, self.ctx.settings.raider_max_minutes, self.stop_event)
            else:
                await run_scripted(persona.base, run, persona, self._emit_thought, self.ctx.state.demo_mode,
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
            await self._roster(name, "idle", self.mode_for(persona_for(name) or BY_NAME[name.partition("-")[0]]))
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
            items = [i for i in self.loot.items if i.raider.partition("-")[0] == persona.name]
            board.append({"raider": persona.name, "mode": self.mode_for(persona), "state": self.persona_state(persona.name),
                          "copies": self.copies_of(persona.name), "loot": len(items),
                          "kinds": sorted({i.kind for i in items})})
        return board

    def copies_of(self, base: str) -> int:
        return sum(1 for name in self.state if name.partition("-")[0] == base)

    def persona_state(self, base: str) -> str:
        """roaming while any copy is out, otherwise the state of copy 1."""
        states = [s for name, s in self.state.items() if name.partition("-")[0] == base]
        return "roaming" if "roaming" in states else self.state.get(base, "idle")
