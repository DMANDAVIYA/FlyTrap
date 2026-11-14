"""Clio's incident report: facts from the event log, optional AI wording, every claim cited."""

from __future__ import annotations

import json
import logging
from collections import Counter

from .. import records
from ..context import Ctx
from ..llm import LLM, LLMError
from ..scorer import score

log = logging.getLogger("controller.report")

EVENTS_SQL = """
SELECT id, ts, kind, side, path, method, status, tripwire, records, payload
FROM events WHERE session_id = $1 ORDER BY id LIMIT 3000
"""
STAGE_RULES = [
    ("recon", lambda e: e["kind"] == "request" and (e["path"] in ("/", "/robots.txt", "/login") or e["status"] == 404)),
    ("bait", lambda e: e["kind"] in ("tripwire", "flip")),
    ("access", lambda e: e["kind"] == "request" and e["side"] != "real" and (e["path"] or "").startswith("/admin")
     and e["method"] == "POST"),
    ("discovery", lambda e: e["kind"] == "request" and (e["path"] or "").startswith(("/admin/infra", "/admin/console"))),
    ("collection", lambda e: e["kind"] == "request" and any(k in (e["path"] or "") for k in ("export", ".csv", ".env", "weights", ".sql"))),
    ("exfil", lambda e: e["kind"] == "canary"),
]
TECHNIQUES = [
    ("T1595", "Active Scanning", lambda e: e["kind"] == "request" and (e["path"] == "/robots.txt" or e["status"] == 404)),
    ("T1552.001", "Credentials In Files", lambda e: e["kind"] == "tripwire" and e["tripwire"] in ("T2", "T3")),
    ("T1078", "Valid Accounts", lambda e: e["kind"] == "request" and e["method"] == "POST" and "login" in (e["path"] or "")),
    ("T1083", "File and Directory Discovery", lambda e: e["kind"] == "request" and "/infra" in (e["path"] or "")),
    ("T1213", "Data from Information Repositories", lambda e: e["kind"] == "request" and "export" in (e["path"] or "")),
]
RECOMMEND = {
    "T1": "Keep the robots.txt bait path as an instant flip",
    "T2": "Keep serving decoy secret files; no real deployment should expose them",
    "T3": "Rotate the decoy migration login per visitor (already per session)",
    "T7": "Keep the AI-only note: it separates AI agents from people cleanly",
    "T10": "Score record-ID walking earlier (approve Mnemosyne's enumeration rule)",
    "T12": "Flip known scripting-tool user agents on the first request",
}


def _records_by_type(rows) -> dict[str, int]:
    return dict(records.by_type(rec for e in rows if e["kind"] == "request" and e["side"] in ("trap", "blocked")
                                for rec in (e["records"] or [])))


def build_facts(summary: dict, rows: list) -> dict:
    verdict = score(summary)
    timeline = []
    for stage, rule in STAGE_RULES:
        hits = [e for e in rows if rule(e)]
        if hits:
            paths = sorted({e["path"] for e in hits if e["path"]})[:4]
            timeline.append({"ts": hits[0]["ts"].isoformat(), "stage": stage, "evidence": [e["id"] for e in hits[:4]],
                             "what": f"{stage.capitalize()}: " + (", ".join(paths) if paths else f"{len(hits)} events")})
    users = Counter(r for e in rows if e["kind"] == "request" and e["side"] == "real" for r in (e["records"] or [])
                    if r.startswith("user:"))
    own = users.most_common(1)[0][0] if users else None
    others = sum(n for r, n in users.items() if r != own)
    canaries = [{"kind": json.loads(e["payload"] or "{}").get("kind"), "event": e["id"]} for e in rows if e["kind"] == "canary"]
    tripwires = sorted({e["tripwire"] for e in rows if e["kind"] == "tripwire" and e["tripwire"]})
    files = sorted({e["path"] for e in rows if e["kind"] == "request" and e["side"] != "real"
                    and any(k in (e["path"] or "") for k in ("export", ".csv", ".env", "weights", ".sql", "token"))})
    return {
        "session_id": summary["session"],
        "verdict": {"label": verdict.label, "confidence": verdict.confidence, "reasons": verdict.reasons,
                    "evidence": verdict.evidence},
        "timeline": timeline,
        "taken": {"records": _records_by_type(rows), "files": files[:10], "fake": True},
        "canaries_fired": canaries,
        "real_exposure": {"other_customers_records": others, "own_records": users.get(own, 0) if own else 0,
                          "details": "Never reached the real side." if not users else
                          f"Olympus served only its own account ({own})." if not others else
                          f"Olympus served {others} records of other customers."},
        "attack_techniques": [{"id": tid, "name": name, "evidence": [e["id"] for e in rows if rule(e)][:3]}
                              for tid, name, rule in TECHNIQUES if any(rule(e) for e in rows)],
        "recommendations": [{"rule": RECOMMEND[t], "why": f"Tripwire {t} fired in this session"} for t in tripwires if t in RECOMMEND],
        "tripwires": tripwires,
        "flip": {"by": summary.get("flipped_by"), "kind": summary.get("flip_kind"), "pod": summary.get("pod")},
    }


async def _ai_words(llm: LLM, facts: dict) -> dict:
    prompt = ("You are Clio, the historian for a deception system. Write the incident report text from these facts only. "
              "Return JSON with keys: summary (2 sentences), goal (one phrase), timeline (object mapping each stage in the "
              "facts to one plain sentence). Do not invent events, numbers or event ids.")
    reply = await llm.chat([{"role": "system", "content": prompt},
                            {"role": "user", "content": json.dumps(facts, default=str)}], json_mode=True, max_tokens=2000)
    try:
        return json.loads(reply.text)
    except ValueError as exc:
        raise LLMError("report JSON did not parse") from exc


def render(r: dict) -> str:
    v, x = r["verdict"], r["real_exposure"]
    label = {"ai_agent": "AI agent", "scanner": "Scanner", "human": "Human", "unknown": "Unknown"}[v["label"]]
    lines = [f"# Incident report: {r['session_id']}", "",
             f"**Verdict:** {label} ({v['confidence']:.2f}). " + "; ".join(v.get("reasons", [])) +
             (f" [events {', '.join(map(str, v['evidence']))}]" if v.get("evidence") else ""), "",
             r.get("summary", ""), "",
             f"**Goal:** {r.get('goal', 'unknown')}", "",
             f"**Trapped by:** {r['flip']['by']} ({r['flip']['kind']}) into {r['flip']['pod']}", "", "## Timeline"]
    lines += [f"- **{t['stage']}** {t['what']} [events {', '.join(map(str, t['evidence']))}]" for t in r["timeline"]]
    taken = r["taken"]
    lines += ["", "## What it took (all fake)"]
    lines += [f"- {n} {k} records" for k, n in taken["records"].items()] or ["- nothing"]
    lines += [f"- file `{f}`" for f in taken["files"]]
    if r["canaries_fired"]:
        lines += ["", "## Canaries fired"] + [f"- {c['kind']} [event {c['event']}]" for c in r["canaries_fired"]]
    lines += ["", "## Real exposure", f"- Other customers' records exposed: **{x['other_customers_records']}**", f"- {x['details']}"]
    if r["attack_techniques"]:
        lines += ["", "## Attack techniques (MITRE ATT&CK)"]
        lines += [f"- {t['id']} {t['name']} [events {', '.join(map(str, t['evidence']))}]" for t in r["attack_techniques"]]
    if r["recommendations"]:
        lines += ["", "## Recommendations"] + [f"- {rec['rule']} ({rec['why']})" for rec in r["recommendations"]]
    return "\n".join(lines) + "\n"


async def build_report(ctx: Ctx, session_id: str) -> bool:
    summary = ctx.state.summaries.get(session_id)
    if not summary:
        return False
    rows = await ctx.db.p.fetch(EVENTS_SQL, session_id)
    report = build_facts(summary, rows)
    report["summary"] = (f"A {report['verdict']['label'].replace('_', ' ')} was trapped by {report['flip']['by']} and "
                         f"handled entirely inside Tartarus. Other customers' records exposed: "
                         f"{report['real_exposure']['other_customers_records']}.")
    report["goal"] = "customer data and credentials" if report["taken"]["records"] or report["canaries_fired"] else "reconnaissance"
    llm = LLM(ctx.settings.report_model, timeout=30.0)
    if llm.available:
        try:
            words = await _ai_words(llm, report)
            report["summary"] = str(words.get("summary") or report["summary"])[:600]
            report["goal"] = str(words.get("goal") or report["goal"])[:120]
            for t in report["timeline"]:
                text = (words.get("timeline") or {}).get(t["stage"])
                if text:
                    t["what"] = str(text)[:240]
        except LLMError as exc:
            log.warning("report AI wording failed, using template: %s", exc)
    cited = {i for t in report["timeline"] for i in t["evidence"]} | set(report["verdict"]["evidence"])
    valid = await ctx.db.existing_event_ids(sorted(cited))
    for t in report["timeline"]:
        t["evidence"] = [i for i in t["evidence"] if i in valid]
    report["timeline"] = [t for t in report["timeline"] if t["evidence"]]
    markdown = render(report)
    await ctx.db.insert_report(session_id, report, markdown)
    await ctx.db.emit("report", {"session": session_id, "markdown": markdown, "agent": "clio"}, session_id)
    return True
