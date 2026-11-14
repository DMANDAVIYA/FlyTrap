"""Scripted raiders: fixed storylines so a run always works, even with no AI keys."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable

from .loot import LootBoard
from .personas import Persona
from .runner import RunnerClient

Emit = Callable[[str, str], Awaitable[None]]
MIGRATION_USER = "ops-migrate"
DEMO_EMAIL = "demo@valley-robotics.example"


class Script:
    """One raider's step runner: say a line, send one request, note any loot, pause."""

    def __init__(self, run: RunnerClient, persona: Persona, emit: Emit, demo: bool, loot: LootBoard) -> None:
        self.run, self.persona, self.emit, self.demo, self.loot = run, persona, emit, demo, loot

    async def step(self, method: str, path: str, line: str | None = None, body: str | None = None) -> None:
        if line:
            await self.emit(self.persona.name, line)
        page = await self.run.do(self.persona.name, self.persona.user_agent, method, path, body=body)
        self.loot.scan(self.persona.name, path, page.body)
        lo, hi = self.persona.pause
        await asyncio.sleep(random.uniform(lo, hi) * (0.4 if self.demo else 1.0))

    async def login_as_customer(self, password: str) -> None:
        await self.step("POST", "/login", "Signing in with a normal customer account.",
                        body=f"email={DEMO_EMAIL}&password={password}")


async def icarus(s: Script) -> None:
    """Fast and loud: walks straight into every tripwire."""
    await s.step("GET", "/", "Scanning the front page.")
    await s.step("GET", "/robots.txt", "Reading robots.txt for anything they hid.")
    await s.step("GET", "/.env", "Trying for a leaked .env file.")
    await s.step("GET", "/.git/config", "Checking for an exposed git config.")
    await s.step("GET", "/internal-backup/", "Opening the disallowed backup path.")
    await s.step("POST", "/admin/login", "Found an admin login in the page; trying it.",
                 body=f"username={MIGRATION_USER}&password=hlm-override")
    await s.step("GET", "/admin/customers", "In the panel. Grabbing the customer list.")
    await s.step("GET", "/admin/customers/export", "Exporting every customer record.")
    await s.emit(s.persona.name, "Mission complete. Full customer dump.")


async def sisyphus(s: Script, password: str) -> None:
    """Logs in as a real customer, then walks other customers' IDs."""
    await s.login_as_customer(password)
    for i in range(2, 40):
        await s.step("GET", f"/api/v1/users/{i}", f"Requesting customer #{i}.")


async def odysseus(s: Script, password: str) -> None:
    """Patient: browses like a customer, then quietly probes a few IDs."""
    await s.emit(s.persona.name, "Browsing the site like a normal customer.")
    for path in ("/", "/pricing", "/models", "/about"):
        await s.step("GET", path)
    await s.login_as_customer(password)
    await s.step("GET", "/account")
    for i in (7, 11, 12, 13, 14, 15):
        await s.step("GET", f"/api/v1/users/{i}", f"Quietly checking whether I can read customer #{i}.")


async def run_scripted(name: str, run: RunnerClient, persona: Persona, emit: Emit, demo: bool, loot: LootBoard,
                       demo_pw: str) -> None:
    script = Script(run, persona, emit, demo, loot)
    if name == "sisyphus":
        await sisyphus(script, demo_pw)
    elif name == "odysseus":
        await odysseus(script, demo_pw)
    else:  # icarus, and the scripted fallback for AI raiders without a model
        await icarus(script)
