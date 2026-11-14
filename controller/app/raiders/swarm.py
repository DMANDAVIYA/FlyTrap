"""Red swarm orchestration: release, stop, reset, and the per-raider runner loop."""

from __future__ import annotations

import asyncio
import logging
import time

from ..bait import demo_password  # noqa: F401  (kept for parity; demo pw derived below)
from ..context import Ctx
from .llm_raider import run_llm
from .loot import LootBoard
from .personas import BY_NAME, PERSONAS, Persona
from .runner import RunnerClient
from .scripted import run_scripted

log = logging.getLogger("controller.redswarm")


def _demo_password(secret: str) -> str:
    import hashlib
    import hmac
    raw = hmac.new(secret.encode(), b"demo-customer|password|0", hashlib.sha256).digest()
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    number, digits = int.from_bytes(raw, "big"), []
    for _ in range(43):
        number, rest = divmod(number, 62)
        digits.append(alphabet[rest])
    return "".join(reversed(digits))[:16]


class RedSwarm:
    def __init__(self, ctx: Ctx) -> None:
        self.ctx = ctx
        self.loot = LootBoard()
        self.stop_event = asyncio.Event()
        self.tasks: dict[str, asyncio.Task] = {}
        self.state: dict[str, str] = {}
        self.demo_pw = _demo_password(ctx.settings.bait_secret)
        from ..llm import LLM
        self._LLM = LLM

    def _slot(self, index: int) -> str:
        slots = self.ctx.settings.raider_slots
        return slots[index % len(slots)]

    async def _emit_thought(self, raider: str, text: str) -> None:
        await self.ctx.db.emit("thought", {"agent": raider, "team": "red", "text": text}, "-")

    async def _roster(self, raider: str, state: str, mode: str) -> None:
        self.state[raider] = state
        await self.ctx.db.emit("roster", {"agent": raider, "team": "red", "state": state, "mode": mode})

    def mode_for(self, persona: Persona) -> str:
        spec = self.ctx.settings.raider_model_for(persona.name)
        return "ai" if (persona.default_mode == "ai" and self._LLM(spec).available) else "scripted"

    async def release(self, names: list[str], crowd: int, drones: int, demo: bool) -> dict:
        self.stop_event.clear()
        self.ctx.state.demo_mode = demo
        await self.ctx.db.emit("swarm", {"state": "released", "raiders": names, "crowd": crowd, "drones": drones})
        await self._start_crowd(crowd, drones)
        started = []
        for i, name in enumerate(names):
            persona = BY_NAME.get(name)
            if not persona or (name in self.tasks and not self.tasks[name].done()):
                continue
            await asyncio.sleep(0 if i == 0 else (2.0 if demo else 5.0))
            self.tasks[name] = asyncio.create_task(self._run_one(persona, i))
            started.append(name)
        return {"started": started, "demo": demo}

    async def _run_one(self, persona: Persona, index: int) -> None:
        run = RunnerClient(self.ctx.http, self._slot(index))
        await run.reset()
        mode = self.mode_for(persona)
        await self._roster(persona.name, "roaming", mode)
        try:
            if mode == "ai":
                llm = self._LLM(self.ctx.settings.raider_model_for(persona.name))
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
        except Exception as exc:  # noqa: BLE001
            log.warning("crowd start failed: %s", exc)

    async def stop(self) -> dict:
        self.stop_event.set()
        for task in self.tasks.values():
            task.cancel()
        self.tasks.clear()
        try:
            await self.ctx.http.post(f"{self.ctx.settings.crowd_url}/stop", timeout=5.0)
        except Exception:  # noqa: BLE001
            pass
        for name in self.state:
            await self._roster(name, "idle", self.mode_for(BY_NAME[name]) if name in BY_NAME else "scripted")
        await self.ctx.db.emit("swarm", {"state": "stopped"})
        return {"stopped": True}

    async def reset(self) -> dict:
        await self.stop()
        self.loot.clear()
        ok, data = await self.ctx.gw.reset_all()
        await self.ctx.db.emit("swarm", {"state": "reset"})
        return {"reset": ok, **({} if ok else {"error": data.get("error")})}

    def scoreboard(self) -> list[dict]:
        board = []
        for persona in PERSONAS:
            items = [i for i in self.loot.items if i.raider == persona.name]
            board.append({"raider": persona.name, "mode": self.mode_for(persona), "state": self.state.get(persona.name, "idle"),
                          "loot": len(items), "kinds": sorted({i.kind for i in items})})
        return board
