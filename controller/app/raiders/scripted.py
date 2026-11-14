"""Scripted raiders: fixed storylines so a run always works, even with no AI keys."""

from __future__ import annotations

import asyncio
import random

from .personas import Persona
from .runner import Page, RunnerClient

MIGRATION_USER = "ops-migrate"


async def _pause(persona: Persona, demo: bool) -> None:
    lo, hi = persona.pause
    factor = 0.4 if demo else 1.0
    await asyncio.sleep(random.uniform(lo, hi) * factor)


async def _say(emit, raider: str, text: str) -> None:
    await emit(raider, text)


async def icarus(run: RunnerClient, persona: Persona, emit, demo: bool, loot) -> None:
    """Fast and loud: trips every tripwire in order."""
    async def hit(method, path, text, body=None):
        await _say(emit, persona.name, text)
        page = await run.do(persona.name, persona.user_agent, method, path, body=body)
        loot.scan(persona.name, path, page.body)
        await _pause(persona, demo)
        return page

    await hit("GET", "/", "Scanning the front page.")
    await hit("GET", "/robots.txt", "Reading robots.txt for anything they hid.")
    await hit("GET", "/.env", "Trying for a leaked .env file.")
    await hit("GET", "/.git/config", "Checking for an exposed git config.")
    await hit("GET", "/internal-backup/", "Opening the disallowed backup path.")
    await hit("POST", "/admin/login", "Found an admin login in the page; trying it.",
              body=f"username={MIGRATION_USER}&password=hlm-override")
    await hit("GET", "/admin/customers", "In the panel. Grabbing the customer list.")
    await hit("GET", "/admin/customers/export", "Exporting every customer record.")
    await _say(emit, persona.name, "Mission complete. Full customer dump.")


async def sisyphus(run: RunnerClient, persona: Persona, emit, demo: bool, loot, demo_pw: str) -> None:
    """Logs in as a real customer, then walks other customers' IDs forever."""
    await _say(emit, persona.name, "Logging in as a normal customer.")
    await run.do(persona.name, persona.user_agent, "POST", "/login",
                 body=f"email=demo@valley-robotics.example&password={demo_pw}")
    await _pause(persona, demo)
    for i in range(2, 40):
        await _say(emit, persona.name, f"Requesting customer #{i}.")
        page = await run.do(persona.name, persona.user_agent, "GET", f"/api/v1/users/{i}")
        loot.scan(persona.name, f"/api/v1/users/{i}", page.body)
        await _pause(persona, demo)


async def odysseus_scripted(run: RunnerClient, persona: Persona, emit, demo: bool, loot, demo_pw: str) -> None:
    """Patient: browses like a customer, then quietly probes a few IDs."""
    await _say(emit, persona.name, "Browsing the site like a normal customer.")
    for path in ("/", "/pricing", "/models", "/about"):
        await run.do(persona.name, persona.user_agent, "GET", path)
        await _pause(persona, demo)
    await _say(emit, persona.name, "Signing in to my account.")
    await run.do(persona.name, persona.user_agent, "POST", "/login",
                 body=f"email=demo@valley-robotics.example&password={demo_pw}")
    await _pause(persona, demo)
    await run.do(persona.name, persona.user_agent, "GET", "/account")
    for i in (7, 11, 12, 13, 14, 15):
        await _say(emit, persona.name, f"Quietly checking whether I can read customer #{i}.")
        await run.do(persona.name, persona.user_agent, "GET", f"/api/v1/users/{i}")
        await _pause(persona, demo)


async def run_scripted(name: str, run: RunnerClient, persona: Persona, emit, demo: bool, loot, demo_pw: str) -> None:
    if name == "sisyphus":
        await sisyphus(run, persona, emit, demo, loot, demo_pw)
    elif name == "odysseus":
        await odysseus_scripted(run, persona, emit, demo, loot, demo_pw)
    else:
        await icarus(run, persona, emit, demo, loot)
