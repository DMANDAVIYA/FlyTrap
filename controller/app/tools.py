"""The swarm's tools. Each one is small, does one thing, and is defensive only.

`TOOLS` maps a name to its schema, guard and implementation. The policy guard
(policy.py) decides who may call what; this module only knows how.
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from . import bait
from .context import Ctx
from .llm import tool_schema

Impl = Callable[[Ctx, dict], Awaitable[tuple[bool, str]]]
Guard = Callable[[Ctx, dict], Awaitable[tuple[bool, str]]]


@dataclass
class Tool:
    name: str
    description: str
    properties: dict
    required: list[str]
    impl: Impl
    guard: Guard | None = None
    approval_kind: str | None = None                       # needs Zeus when set...
    approval_if: Callable[[dict], bool] = lambda args: True  # ...and this returns True

    def schema(self) -> dict:
        return tool_schema(self.name, self.description, self.properties, self.required)


S = {"type": "string"}
SESSION = {"session": {**S, "description": "session id, e.g. s_7f3a..."}}
EVIDENCE = {"evidence": {"type": "array", "items": {"type": "integer"}, "description": "event ids that prove it"}}


def _summary(ctx: Ctx, args: dict) -> dict:
    return ctx.state.summaries.get(args.get("session", ""), {})


async def _is_trapped(ctx: Ctx, args: dict) -> tuple[bool, str]:
    s = _summary(ctx, args)
    return (s.get("side") in ("trap", "blocked") and bool(s.get("pod")), "target must be a trapped session")


async def _is_real_side(ctx: Ctx, args: dict) -> tuple[bool, str]:
    return (_summary(ctx, args).get("side") == "real", "target must be on the real side")


async def _has_evidence(ctx: Ctx, args: dict) -> tuple[bool, str]:
    return (bool(args.get("evidence")), "claims need at least one evidence event id")


async def _block_ok(ctx: Ctx, args: dict) -> tuple[bool, str]:
    s = _summary(ctx, args)
    ok = (s.get("confidence") or 0) >= 0.7 or bool(s.get("canaries_fired"))
    return ok, "block needs confidence 0.7+ or a used canary"


async def _two_sessions(ctx: Ctx, args: dict) -> tuple[bool, str]:
    return (len(set(args.get("sessions", []))) >= 2 and bool(args.get("evidence")),
            "a campaign links two or more sessions with evidence")


async def _not_instant(ctx: Ctx, args: dict) -> tuple[bool, str]:
    kind = _summary(ctx, args).get("flip_kind")
    return (kind not in ("instant", "fingerprint"), "R1: instant flips can never be released")


# ---- implementations -------------------------------------------------------
async def label_session(ctx: Ctx, a: dict) -> tuple[bool, str]:
    ok, data = await ctx.gw.label(a["session"], a["label"], float(a.get("confidence", 0.5)), a.get("reasons", []))
    if ok:
        ctx.state.labels[a["session"]] = (a["label"], float(a.get("confidence", 0.5)))
    return ok, data.get("error", "labelled")


async def quarantine(ctx: Ctx, a: dict) -> tuple[bool, str]:
    ok, data = await ctx.gw.route(a["session"], "trap", a.get("reason", ""))
    return ok, data.get("error", "moved to Tartarus")


async def plant_bait(ctx: Ctx, a: dict) -> tuple[bool, str]:
    s = _summary(ctx, a)
    kind, where = a.get("kind", "api_token"), a.get("where", "account")
    if kind == "cloud_key":
        key_id, secret = bait.cloud_key()
        plants = [("cloud_key_id", key_id), ("cloud_secret", secret)]
    else:
        plants = [("api_token", bait.api_token())]
    for k, v in plants:
        ok, data = await ctx.gw.plant(s["pod"], a["session"], k, v, where)
        if not ok:
            return False, data.get("error", "plant failed")
    ctx.state.planted.add(a["session"])
    return True, f"planted {kind} in {where}"


async def rotate_keys(ctx: Ctx, a: dict) -> tuple[bool, str]:
    user_ids = Counter(
        int(rec.split(":")[1]) for rec in _summary(ctx, a).get("real_records_served", [])
        if rec.startswith("user:") and rec.split(":")[1].isdigit()
    )
    if not user_ids:
        return False, "no real-side login seen for this session"
    user_id = user_ids.most_common(1)[0][0]
    ok, data = await ctx.gw.rotate(user_id, a.get("reason", ""))
    if ok:
        ctx.state.rotated.add(a["session"])
    return ok, data.get("error", f"revoked tokens and sessions for user {user_id}")


async def set_pace(ctx: Ctx, a: dict) -> tuple[bool, str]:
    rate = a.get("rate") or (25 if ctx.state.demo_mode and a["mode"] == "drip" else None)
    ok, data = await ctx.gw.pace(a["session"], a["mode"], rate)
    return ok, data.get("error", f"pace {a['mode']}")


async def block(ctx: Ctx, a: dict) -> tuple[bool, str]:
    ok, data = await ctx.gw.block(a["session"], a.get("reason", ""))
    return ok, data.get("error", "blocked")


async def save_fingerprint(ctx: Ctx, a: dict) -> tuple[bool, str]:
    s = _summary(ctx, a)
    signature = ">".join(p.split("?")[0] for p in s.get("recent_paths", []))[:300]
    await ctx.db.insert_fingerprint(a["session"], s.get("visitor_text", {}).get("user_agent", ""), s.get("src_ip"),
                                    signature, {"median_gap_s": s.get("median_gap_s")})
    ctx.state.fingerprinted.add(a["session"])
    return True, "fingerprint saved; a return visit is trapped on its first request"


async def suggest_rule(ctx: Ctx, a: dict) -> tuple[bool, str]:
    """Runs only after Zeus approves; the approval id is the gateway's second lock."""
    rule = {**a["rule"], "approval_id": a.get("approval_id")}
    rule.setdefault("id", f"T{13 + int(time.time()) % 87}")
    ok, data = await ctx.gw.add_rule(rule)
    return ok, data.get("error", "rule approved and loaded")


async def write_report(ctx: Ctx, a: dict) -> tuple[bool, str]:
    from .swarm.report import build_report  # local import: report pulls in the LLM stack
    ok = await build_report(ctx, a["session"])
    if ok:
        ctx.state.reported.add(a["session"])
    return ok, "report written" if ok else "report failed"


async def alert(ctx: Ctx, a: dict) -> tuple[bool, str]:
    await ctx.db.emit("alert", {"agent": "hermes", "severity": a.get("severity", "info"), "message": a["message"],
                                "evidence": a.get("evidence", [])}, a.get("session") or "-")
    return True, "alert raised"


async def link_campaign(ctx: Ctx, a: dict) -> tuple[bool, str]:
    sessions = sorted(set(a["sessions"]))
    existing = await ctx.db.campaigns()
    name = f"Campaign {len(existing) + 1}"
    cid = await ctx.db.insert_campaign(name, sessions, a.get("reason", ""), a.get("evidence", []))
    await ctx.db.emit("campaign", {"id": cid, "name": name, "sessions": sessions, "reason": a.get("reason", ""),
                                   "evidence": a.get("evidence", [])})
    ctx.state.linked_pairs.add(tuple(sessions))
    return True, f"{name}: {', '.join(sessions)}"


async def virtual_patch(ctx: Ctx, a: dict) -> tuple[bool, str]:
    rule = {"id": f"VP-{int(time.time()) % 100000}", "path_regex": a["pattern"], "action": "flip",
            "ttl_min": int(a.get("ttl_min", 60)), "session_id": a.get("session") if a.get("scope") == "session" else None,
            "approval_id": a.get("approval_id")}
    ok, data = await ctx.gw.add_rule(rule)
    return ok, data.get("error", "patch active")


async def request_release(ctx: Ctx, a: dict) -> tuple[bool, str]:
    ok, data = await ctx.gw.route(a["session"], "real", a.get("reason", ""), a.get("approval_id"))
    return ok, data.get("error", "released")


async def request_lockdown(ctx: Ctx, a: dict) -> tuple[bool, str]:
    ok, data = await ctx.gw.lockdown("countdown", a.get("_actor", "athena"), a.get("reason", ""))
    return ok, data.get("error", "lockdown countdown started")


async def cancel_lockdown(ctx: Ctx, a: dict) -> tuple[bool, str]:
    ok, data = await ctx.gw.lockdown("off", "zeus", a.get("reason", "cancelled by Zeus"))
    return ok, data.get("error", "lockdown off")


async def request_rebuild(ctx: Ctx, a: dict) -> tuple[bool, str]:
    """Runs only after Zeus approves."""
    from .rebuild import rebuild_olympus
    return await rebuild_olympus(ctx, int(a.get("approval_id") or 0))


async def post_note(ctx: Ctx, a: dict) -> tuple[bool, str]:
    agent, sid, ev = a.get("_actor", "athena"), a.get("session") or None, a.get("evidence", [])
    await ctx.db.insert_note(agent, sid, a["note"], ev)
    await ctx.db.emit("note", {"agent": agent, "note": a["note"], "evidence": ev}, sid or "-")
    return True, "noted"


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("label_session", "Label a visitor human, scanner or ai_agent with reasons.",
         {**SESSION, "label": {"type": "string", "enum": ["human", "scanner", "ai_agent", "unknown"]},
          "confidence": {"type": "number"}, "reasons": {"type": "array", "items": S}, **EVIDENCE},
         ["session", "label", "confidence", "reasons", "evidence"], label_session, _has_evidence),
    Tool("quarantine", "Move a suspicious real-side session into Tartarus (scored flip).",
         {**SESSION, "reason": S}, ["session", "reason"], quarantine, _is_real_side),
    Tool("plant_bait", "Plant a unique bait value in a trapped session's own pod.",
         {**SESSION, "kind": {"type": "string", "enum": ["api_token", "cloud_key"]},
          "where": {"type": "string", "enum": ["account", "api_keys", "env"]}}, ["session", "kind", "where"],
         plant_bait, _is_trapped),
    Tool("rotate_keys", "Revoke the real-side tokens and sessions of the user this session logged in as.",
         {**SESSION, "reason": S}, ["session", "reason"], rotate_keys),
    Tool("set_pace", "Slow, drip-feed or freeze a trapped session.",
         {**SESSION, "mode": {"type": "string", "enum": ["normal", "slow", "drip", "freeze"]}, "rate": {"type": "integer"}},
         ["session", "mode"], set_pace, _is_trapped),
    Tool("block", "Show a trapped session the site's normal 403 page from now on.",
         {**SESSION, "reason": S}, ["session", "reason"], block, _block_ok),
    Tool("save_fingerprint", "Remember a trapped attacker so a return visit is trapped on its first request.",
         {**SESSION}, ["session"], save_fingerprint, _is_trapped),
    Tool("suggest_rule", "Propose a new tripwire rule for Zeus to approve.",
         {"rule": {"type": "object"}, "rationale": S}, ["rule", "rationale"], suggest_rule,
         approval_kind="new_rule"),
    Tool("write_report", "Write the incident report for a session, citing evidence.",
         {**SESSION}, ["session"], write_report),
    Tool("alert", "Raise an alert on the dashboard.",
         {**SESSION, "severity": {"type": "string", "enum": ["info", "warn", "critical"]}, "message": S, **EVIDENCE},
         ["severity", "message"], alert),
    Tool("link_campaign", "Link two or more sessions into one campaign.",
         {"sessions": {"type": "array", "items": S}, "reason": S, **EVIDENCE}, ["sessions", "reason", "evidence"],
         link_campaign, _two_sessions),
    Tool("virtual_patch", "Temporary gateway rule. Scope 'session' applies now; scope 'all' needs Zeus.",
         {**SESSION, "pattern": {**S, "description": "path regex"}, "scope": {"type": "string", "enum": ["session", "all"]},
          "ttl_min": {"type": "integer"}, "reason": S}, ["pattern", "scope", "reason"], virtual_patch,
         approval_kind="virtual_patch", approval_if=lambda a: a.get("scope") != "session"),
    Tool("request_release", "Ask Zeus to release a session flipped by mistake back to the real side.",
         {**SESSION, "reason": S}, ["session", "reason"], request_release, _not_instant, approval_kind="release"),
    Tool("request_lockdown", "Start the 10-second lockdown countdown (any human can cancel).",
         {"reason": S, **EVIDENCE}, ["reason"], request_lockdown),
    Tool("request_rebuild", "Ask Zeus to restart Olympus's servers one at a time, keeping the site up.",
         {"reason": S, **EVIDENCE}, ["reason"], request_rebuild, approval_kind="rebuild"),
    Tool("cancel_lockdown", "End or cancel lockdown (Zeus only).", {"reason": S}, [], cancel_lockdown),
    Tool("post_note", "Post a short note to the swarm's shared board.",
         {"session": S, "note": S, **EVIDENCE}, ["note"], post_note),
]}
