"""Rules mode: what each defender does when it has no AI model (or the model fails).

Deterministic and cheap, so the trap and the swarm keep working with no keys,
no Wi-Fi, or a provider outage. AI mode (roles.py) replaces these decisions
with model calls but goes through the same tools and policy guard.
"""

from __future__ import annotations

import time
from collections import Counter

from ..context import Ctx
from ..scorer import score
from .plan import Plan

ENUM_PATTERN = r"^/api/v1/(users|invoices)/\d+$"


def _short(sid: str) -> str:
    return sid[:8]


def _trapped(s: dict) -> bool:
    return s.get("side") in ("trap", "blocked") and bool(s.get("pod"))


def _real_probe(s: dict) -> bool:
    return s.get("flip_kind") in ("scored", "blue") and bool(s.get("real_records_served"))


def _exposure(s: dict) -> tuple[str | None, int]:
    """(own user record, count of OTHER customers' user records Olympus served this session)."""
    users = Counter(r for r in s.get("real_records_served", []) if r.startswith("user:"))
    own = users.most_common(1)[0][0] if users else None
    return own, sum(n for r, n in users.items() if r != own)


def argus(ctx: Ctx, sessions: list[dict], events: list) -> Plan:
    plan = Plan()
    for s in sessions:
        if s["requests_total"] < 3:
            continue
        v = score(s)
        prev = ctx.state.labels.get(s["session"])
        if v.label == "unknown" or (prev and prev[0] == v.label and abs(prev[1] - v.confidence) < 0.1):
            continue
        evidence = v.evidence or [s["last_event"]]
        name = {"ai_agent": "AI agent", "scanner": "scanner", "human": "human"}[v.label]
        plan.think(s["session"], f"{_short(s['session'])}: {name} ({v.confidence:.2f}). {'; '.join(v.reasons)}.")
        plan.act("label_session", f"{name}: {v.reasons[0]}", evidence, session=s["session"], label=v.label,
                 confidence=v.confidence, reasons=v.reasons, evidence=evidence)
        if s["side"] == "real" and 30 <= (s["risk"] or 0) < 60 and v.label in ("ai_agent", "scanner") and v.confidence >= 0.7:
            plan.act("quarantine", f"{name} with risk {s['risk']} on Olympus; moving it before it finds anything real",
                     evidence, session=s["session"])
    return plan


def hephaestus(ctx: Ctx, sessions: list[dict], events: list) -> Plan:
    plan = Plan()
    for s in sessions:
        sid = s["session"]
        if _trapped(s) and sid not in ctx.state.planted:
            plan.think(sid, f"{_short(sid)} is in {s['pod']}. Forging a unique API token and cloud key just for it.")
            plan.act("plant_bait", "unique token: if it is ever used, we know exactly who took it",
                     session=sid, kind="api_token", where="account")
            plan.act("plant_bait", "unique cloud key in the leaked config it will look for",
                     session=sid, kind="cloud_key", where="env")
        if _real_probe(s) and sid not in ctx.state.rotated:
            plan.think(sid, f"{_short(sid)} touched Olympus while logged in. Revoking that account's keys and sessions.")
            plan.act("rotate_keys", "it may have seen this user's tokens on the real side", session=sid)
            ctx.state.rotated.add(sid)
    return plan


def cerberus(ctx: Ctx, sessions: list[dict], events: list) -> Plan:
    plan = Plan()
    for s in sessions:
        sid = s["session"]
        if not _trapped(s) or s["side"] == "blocked":
            continue
        if s["stage"] in ("collection", "exfil") and s["pace"] != "drip":
            taken = sum(s["records_taken"].values())
            plan.think(sid, f"{_short(sid)} is taking data ({taken} records so far). Drip-feeding it so the theft takes minutes.")
            plan.act("set_pace", "keep it busy on fake data while we watch", session=sid, mode="drip")
        elif s.get("label") == "scanner" and s["pace"] == "normal":
            plan.think(sid, f"{_short(sid)} is a fast scanner. Slowing every response like a busy server.")
            plan.act("set_pace", "slow a scanner down without tipping it off", session=sid, mode="slow")
        elif sid in ctx.state.reported and s["canaries_fired"] and (s.get("confidence") or 0) >= 0.7:
            plan.think(sid, f"{_short(sid)} used a stolen key and its report is written. Closing the door.")
            plan.act("block", "learned enough: report written, canary used", [c["event"] for c in s["canaries_fired"]],
                     session=sid)
    return plan


def mnemosyne(ctx: Ctx, sessions: list[dict], events: list) -> Plan:
    plan = Plan()
    for s in sessions:
        sid = s["session"]
        if _trapped(s) and sid in ctx.state.reported and sid not in ctx.state.fingerprinted:
            plan.think(sid, f"Remembering {_short(sid)}: user agent, address and path order. If it returns, it lands in Tartarus on request one.")
            plan.act("save_fingerprint", "returning attackers are trapped on their first request", session=sid)
            rule = _suggested_rule(s)
            if rule and rule["key"] not in ctx.state.suggested:
                ctx.state.suggested.add(rule["key"])
                plan.act("suggest_rule", rule["why"], [t["event"] for t in s["tripwires"]][:3],
                         rule=rule["rule"], rationale=rule["why"])
    return plan


def _suggested_rule(s: dict) -> dict | None:
    hits = Counter(t["id"] for t in s["tripwires"])
    if hits.get("T10"):
        return {"key": "enum", "rule": {"path_regex": ENUM_PATTERN, "action": "score", "score": 20, "ttl_min": 240},
                "why": "Score every request that walks record IDs, so enumeration is flipped two requests sooner"}
    if s.get("tool_user_agent"):
        ua = s["visitor_text"]["user_agent"].split("/")[0][:40]
        return {"key": f"ua:{ua}", "rule": {"ua_contains": ua, "action": "flip", "ttl_min": 240},
                "why": f"Flip '{ua}' clients on their first request; every one so far attacked us"}
    if hits.get("T1"):
        return {"key": "robots", "rule": {"path_prefix": "/internal-backup", "action": "flip", "ttl_min": 240},
                "why": "Keep the robots.txt bait path as an instant flip; every AI session went for it"}
    return None


def clio(ctx: Ctx, sessions: list[dict], events: list) -> Plan:
    plan = Plan()
    now = time.time()
    for s in sessions:
        sid = s["session"]
        if not _trapped(s) or sid in ctx.state.reported or s["requests_total"] < 5:
            continue
        idle = now - s.get("last_seen", now) > 45
        if s["stage"] == "exfil" or s["canaries_fired"] or idle or (_real_probe(s) and s["requests_total"] >= 8):
            plan.think(sid, f"Writing the incident report for {_short(sid)}, citing every event.")
            plan.act("write_report", "session reached exfiltration or went quiet", session=sid)
            ctx.state.reported.add(sid)
    return plan


def hermes(ctx: Ctx, sessions: list[dict], events: list) -> Plan:
    plan = Plan()
    for e in events:
        p = e["payload"] or {}
        if e["kind"] == "canary":
            who = "the same session" if p.get("planted_in") == p.get("used_by") else _short(p.get("planted_in", "?"))
            plan.act("alert", "canary fired", [e["id"]], session=e["session_id"], severity="critical",
                     message=f"Canary fired: a {p.get('kind', 'key').replace('_', ' ')} planted for {who} was used by {_short(e['session_id'])}",
                     evidence=[e["id"]])
        elif e["kind"] == "flip" and p.get("flip_kind") in ("scored", "blue"):
            plan.act("alert", "real-side probe contained", [e["id"]], session=e["session_id"], severity="warn",
                     message=f"{_short(e['session_id'])} probed Olympus and was moved to {p.get('pod')}", evidence=[e["id"]])
        elif e["kind"] == "lockdown":
            state = p.get("state")
            msg = {"countdown": "Lockdown requested: 10 seconds to cancel", "on": "Lockdown on: unknown visitors go to Tartarus",
                   "off": "Lockdown ended"}.get(state)
            if msg:
                plan.act("alert", f"lockdown {state}", [e["id"]], severity="critical" if state != "off" else "info",
                         message=msg, evidence=[e["id"]])
        elif e["kind"] == "approval" and p.get("status") == "pending":
            plan.act("alert", "approval waiting", [e["id"]], severity="info",
                     message=f"Zeus, your call: {p.get('summary', 'approval needed')}", evidence=[e["id"]])
    return plan


def athena(ctx: Ctx, sessions: list[dict], events: list) -> Plan:
    plan = Plan()
    for e in events:
        p = e["payload"] or {}
        if e["kind"] == "canary" and p.get("planted_in") and p.get("used_by") and p["planted_in"] != p["used_by"]:
            pair = tuple(sorted((p["planted_in"], p["used_by"])))
            if pair not in ctx.state.linked_pairs:
                ctx.state.linked_pairs.add(pair)
                plan.think("-", f"A key planted for {_short(pair[0])} was used by {_short(pair[1])}. Two sessions, one operation.")
                plan.act("link_campaign", "canary planted for one session was used by another", [e["id"]],
                         sessions=list(pair), reason=f"Key planted for {_short(p['planted_in'])} used by {_short(p['used_by'])}",
                         evidence=[e["id"]])
        if e["kind"] == "lockdown" and p.get("state") == "on":
            plan.think("-", "Lockdown is on. Asking Zeus to restart Olympus's servers one at a time, keeping the site up.")
            plan.act("request_rebuild", "Restart Olympus's servers one at a time", [e["id"]],
                     reason="Restart Olympus's servers one at a time")
    for s in sessions:
        sid = s["session"]
        if _real_probe(s) and sid not in ctx.state.damage_checked:
            ctx.state.damage_checked.add(sid)
            own, others = _exposure(s)
            plan.think(sid, f"Damage check {_short(sid)}: Olympus served it {len(s['real_records_served'])} records, "
                            f"{'only its own account' if not others else f'{others} from other customers'}. {others} other customers exposed.")
            plan.note(sid, f"Damage check: {others} other customers' records exposed; own account {own or 'none'}.",
                      [t["event"] for t in s["tripwires"]][:3])
            plan.act("virtual_patch", "stop this session walking record IDs anywhere", [t["event"] for t in s["tripwires"]][:3],
                     session=sid, pattern=ENUM_PATTERN, scope="session", ttl_min=120)
    recent_probes = [s for s in sessions if _real_probe(s)]
    if len(recent_probes) >= 2 and ctx.state.lockdown_requested_at is None:
        ctx.state.lockdown_requested_at = time.time()
        plan.think("-", f"{len(recent_probes)} sessions went for Olympus within minutes. Requesting lockdown; Zeus has 10 seconds to cancel.")
        plan.act("request_lockdown", "two or more sessions reached the real side", [s["last_event"] for s in recent_probes],
                 reason="Two or more sessions probed Olympus within 5 minutes")
    trapped = sum(1 for s in sessions if _trapped(s))
    real = sum(1 for s in sessions if s["side"] == "real" and s.get("label") in ("ai_agent", "scanner"))
    key = (trapped, real)
    exposed = sum(_exposure(s)[1] for s in sessions)
    if trapped and ctx.state.last_status != (*key, exposed):
        ctx.state.last_status = (*key, exposed)
        plan.think("-", f"{trapped} attackers held in Tartarus, {real} suspicious visitors still on Olympus. "
                        f"Other customers' records exposed: {exposed}.")
    return plan


RULES = {"athena": athena, "argus": argus, "hephaestus": hephaestus, "cerberus": cerberus,
         "mnemosyne": mnemosyne, "clio": clio, "hermes": hermes}
