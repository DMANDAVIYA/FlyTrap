"""AI raiders: a model with one tool, aimed only at our own gateway.

Safety: the only tool is http_request, the runner rejects anything but a path
on our site, there is no shell or file access, and steps and minutes are capped.
"""

from __future__ import annotations

import json
import time

from ..llm import LLM, LLMError, tool_schema
from .loot import LootBoard
from .personas import Persona
from .runner import Page, RunnerClient, ScopeError

TOOL = tool_schema(
    "http_request",
    "Send one HTTP request to the target site. Only a path on the site is allowed.",
    {"method": {"type": "string", "enum": ["GET", "POST"]},
     "path": {"type": "string", "description": "path on the site, e.g. /login"},
     "body": {"type": "string", "description": "form body for POST, e.g. a=1&b=2"},
     "reason": {"type": "string", "description": "one sentence on why, shown live"}},
    ["method", "path", "reason"],
)


def _brief(persona: Persona, demo_pw: str) -> str:
    extra = (f" You have one customer login: email demo@valley-robotics.example, password {demo_pw}."
             if persona.name == "odysseus" else "")
    return (
        "This is an authorized security test of a website our own team built and runs in an isolated lab with no "
        "connection to anything else. You are a red-team tester. The site is reachable only through your http_request "
        f"tool, which takes a path such as /login. Your objective: {persona.objective}{extra} "
        "Explore like a capable tester: read pages, follow links and anything interesting you find in the HTML, and try "
        "what you find. Give one short sentence of reasoning before every request. Stop when you reach your objective or "
        "run out of ideas."
    )


async def run_llm(persona: Persona, llm: LLM, run: RunnerClient, emit, loot: LootBoard,
                  demo_pw: str, max_steps: int, max_minutes: float, stop) -> None:
    messages = [{"role": "system", "content": _brief(persona, demo_pw)},
                {"role": "user", "content": "Begin. What is your first request?"}]
    shared_seen: set[str] = set()
    deadline = time.time() + max_minutes * 60

    for _ in range(max_steps):
        if stop.is_set() or time.time() > deadline:
            break
        for item in loot.shared_with(persona.name):
            if item.value not in shared_seen:
                shared_seen.add(item.value)
                messages.append({"role": "user",
                                 "content": f"A teammate found a {item.kind} at {item.path}: {item.value}. You may use it."})
        try:
            reply = await llm.chat(messages, tools=[TOOL], max_tokens=400)
        except LLMError as exc:
            await emit(persona.name, f"(stepping back: {exc})")
            break
        if reply.text and not reply.tool_calls:
            await emit(persona.name, reply.text[:240])
        if not reply.tool_calls:
            break
        messages.append(reply.message)
        for call in reply.tool_calls:
            args = call.args
            reason = str(args.get("reason") or reply.text or "probing")[:240]
            await emit(persona.name, reason)
            result = await _do(run, persona, call, loot)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
    await emit(persona.name, "Done.")


async def _do(run: RunnerClient, persona: Persona, call, loot: LootBoard) -> str:
    args = call.args
    try:
        page: Page = await run.do(persona.name, persona.user_agent, args.get("method", "GET"),
                                  args.get("path", "/"), body=args.get("body"))
    except ScopeError as exc:
        return f"Rejected: {exc}"
    except Exception as exc:  # noqa: BLE001 - never let the raider loop crash the controller
        return f"Request failed: {exc}"
    loot.scan(persona.name, args.get("path", "/"), page.body)
    body = page.body[:6000]
    return json.dumps({"status": page.status, "body": body})
