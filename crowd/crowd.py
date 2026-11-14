"""Simulated customers and drones, so the map looks like real traffic.

Customers browse normally (keep cookies, load assets, send the beacon) and
never touch bait, so they stay on the real side. Drones are loud scanners.
All of it only ever reaches our own gateway.
"""

from __future__ import annotations

import asyncio
import os
import random

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

GATEWAY = os.getenv("GATEWAY_URL", "http://gateway:8080")
BROWSERS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.{b}.{p} Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.{b}.{p} Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.{p}; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0.{p}",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.{p} Safari/605.1.15",
]


def browser_ua(n: int) -> str:
    """Every simulated customer has its own user agent: they share one IP, so identical UAs would
    collapse their first cookie-less requests into one fingerprint session (and one fast 'visitor')."""
    return BROWSERS[n % len(BROWSERS)].format(b=6700 + n * 13, p=n)


PAGES = ["/", "/pricing", "/models", "/about", "/login", "/account", "/contact"]
ASSETS = ["/static/site.css", "/static/px.js"]
app = FastAPI(docs_url=None, redoc_url=None)
tasks: list[asyncio.Task] = []


class StartIn(BaseModel):
    customers: int = 30
    drones: int = 0
    demo: bool = True


async def customer(n: int, demo: bool) -> None:
    """One simulated customer: its own user agent and its own cookie jar (one client per customer)."""
    ua = browser_ua(n)
    async with httpx.AsyncClient(base_url=GATEWAY, timeout=15.0) as c:
        while True:
            try:
                page = random.choice(PAGES)
                await c.get(page, headers={"user-agent": ua})
                for asset in ASSETS:
                    await c.get(asset, headers={"user-agent": ua})
                await c.post("/_hl/px", json={"js": 1, "mouse": random.randint(3, 40), "keys": random.randint(0, 12)},
                             headers={"user-agent": ua})
            except httpx.HTTPError:
                pass
            await asyncio.sleep(random.uniform(1.5, 6.0) * (0.5 if demo else 1.0))


async def drone(demo: bool) -> None:
    ua = "Mozilla/5.0 (compatible; scan-bot/3.1)"
    probes = ["/admin", "/wp-login.php", "/.env", "/api/v1/users/1", "/backup.zip", "/phpmyadmin", "/server-status"]
    async with httpx.AsyncClient(base_url=GATEWAY, timeout=15.0) as c:
        while True:
            try:
                await c.get(random.choice(probes), headers={"user-agent": ua})
            except httpx.HTTPError:
                pass
            await asyncio.sleep(random.uniform(0.3, 1.2) * (0.5 if demo else 1.0))


@app.post("/start")
async def start(body: StartIn):
    await _stop()
    for n in range(body.customers):
        tasks.append(asyncio.create_task(customer(n, body.demo)))
        await asyncio.sleep(0.05)
    for _ in range(body.drones):
        tasks.append(asyncio.create_task(drone(body.demo)))
    return {"customers": body.customers, "drones": body.drones}


async def _stop() -> None:
    for t in tasks:
        t.cancel()
    tasks.clear()


@app.post("/stop")
async def stop():
    await _stop()
    return {"stopped": True}


@app.get("/healthz")
async def healthz():
    return {"ok": True, "running": len(tasks)}
