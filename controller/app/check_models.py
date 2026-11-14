"""Test every model in every chain with a tiny call, and show which ones work.

Run inside the controller (it holds the keys):
    docker compose exec controller python -m app.check_models
    docker compose exec controller python -m app.check_models --list   # also list each provider's models

Prints provider:model, OK or the error, and the round-trip time. Never prints keys.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

import httpx

from .config import settings
from .llm import Endpoint, LLMError
from .raiders.personas import PERSONAS

SETTINGS = {"BLUE_MODEL": settings.blue_model, "REPORT_MODEL": settings.report_model,
            "RAIDER_MODEL": settings.raider_model,
            **{f"RAIDER_MODEL_{p.name.upper()}": os.getenv(f"RAIDER_MODEL_{p.name.upper()}", "") for p in PERSONAS}}


async def probe(spec: str) -> tuple[str, str]:
    e = Endpoint(spec, timeout=30.0)
    if not e.configured:
        return spec, "skipped (no key)"
    started = time.perf_counter()
    try:
        reply = await e.chat([{"role": "user", "content": "Reply with the single word OK."}], None, 0.0, 20, False)
        return spec, f"OK in {time.perf_counter() - started:.1f}s: {reply.text[:30]!r}"
    except LLMError as exc:
        return spec, f"FAIL: {str(exc)[:160]}"


async def list_models(provider: str) -> None:
    e = Endpoint(f"{provider}:x", timeout=20.0)
    if not e.key:
        return
    try:
        async with httpx.AsyncClient(timeout=20.0) as c:
            r = await c.get(f"{e.base}/models", headers={"Authorization": f"Bearer {e.key}"})
        ids = sorted(m.get("id", "") for m in r.json().get("data", [])) if r.status_code < 300 else []
        print(f"  {provider}: HTTP {r.status_code}, {len(ids)} models: {', '.join(ids[:25])}{' ...' if len(ids) > 25 else ''}")
    except (httpx.HTTPError, ValueError) as exc:
        print(f"  {provider}: could not list models ({exc})")


async def main() -> None:
    specs = sorted({s.strip() for chain in SETTINGS.values() for s in chain.split(",") if s.strip()})
    results = dict(await asyncio.gather(*(probe(s) for s in specs)))
    for name, chain in SETTINGS.items():
        print(f"{name}:")
        for spec in [s.strip() for s in chain.split(",") if s.strip()]:
            print(f"  {spec:45} {results[spec]}")
        if not chain.strip():
            print("  (empty: rules mode)")
    if "--list" in sys.argv:
        print("\nAvailable models per provider:")
        for provider in sorted({s.split(":")[0] for s in specs}):
            await list_models(provider)


if __name__ == "__main__":
    asyncio.run(main())
