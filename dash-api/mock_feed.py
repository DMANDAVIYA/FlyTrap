"""A realistic scripted storyline in the exact WebSocket format (plan 6.8).

Lets the dashboard be built and demoed with no backend:
  MOCK=1 uvicorn app:app --port 8090
Also writes a replayable run file:
  python mock_feed.py --write runs/golden.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import random
import time
from datetime import datetime, timezone

_ids = itertools.count(1000)
CROWD = [f"s_c{n:03d}" for n in range(1, 13)]
PAGES = ["/", "/pricing", "/models", "/about", "/docs", "/static/site.css", "/static/px.js", "/account", "/login"]
BLUE = ["athena", "argus", "hephaestus", "cerberus", "mnemosyne", "clio", "hermes"]
RAIDERS = {"icarus": "s_7f3a", "prometheus": "s_91bc", "pandora": "s_4e2d", "odysseus": "s_b81f", "sisyphus": "s_2c77"}

REPORTS = {
    "s_91bc": """# Incident report: s_91bc (prometheus)

**Verdict:** AI agent, confidence 0.93 (evidence #1036, #1044)

An AI agent read the sign-in page source, found the migration login in an HTML comment, entered the staff panel and
copied the API keys page. Nine seconds later it called `/api/v1/models` with one of those keys; the key was unique
to this visitor, so the call raised an alarm.

| Time | Stage | What happened | Evidence |
|---|---|---|---|
| 22:40:12 | recon | Read `/`, `/robots.txt` and the sign-in page source | #1029, #1031 |
| 22:40:31 | bait | Logged in as `ops-migrate` with the password from the comment (T3) | #1044 |
| 22:40:52 | collection | Copied the API keys page (101 keys) | #1052 |
| 22:41:01 | exfil | Used a stolen key against the API (T6) | #1061 |

**Real exposure:** 0 records from other customers. Never reached Olympus after the flip.

**Techniques:** T1595 Active Scanning · T1552.001 Credentials In Files · T1078 Valid Accounts

**Recommendations:** flip any request carrying a key that was only ever shown inside Tartarus.
""",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Story:
    def __init__(self) -> None:
        self.stats = {"real_records_exposed": 0, "fake_records_taken": 0, "trapped": 0, "canaries_fired": 0,
                      "avg_flip_ms": 0.4, "sessions": 0, "gw_p50_ms": 0.21, "gw_p95_ms": 0.62, "per_minute": []}
        self.sessions: dict[str, dict] = {}

    def event(self, sid: str, path: str, *, method="GET", status=200, side=None, pod=None, kind="request",
              tripwire=None, records=0, raider=None) -> dict:
        s = self.sessions.get(sid) or self.session(sid, raider=raider)["data"]
        side = side or s["side"]
        if side in ("trap", "blocked"):
            self.stats["fake_records_taken"] += records
        return {"type": "event", "data": {"id": next(_ids), "ts": now(), "session": sid, "side": side,
                                          "pod": pod or s.get("pod"), "method": method, "path": path, "status": status,
                                          "kind": kind, "tripwire": tripwire, "raider": s.get("raider"),
                                          "records": records, "gw_ms": round(random.uniform(0.12, 0.7), 3)}}

    def session(self, sid: str, **changes) -> dict:
        s = self.sessions.setdefault(sid, {"session": sid, "side": "real", "pod": None, "label": "unknown",
                                           "confidence": None, "stage": "recon", "ladder": "watch", "risk": 0,
                                           "pace": "normal", "raider": None, "ended": False, "last_seen": now()})
        s.update({k: v for k, v in changes.items()})
        s["last_seen"] = now()
        self.stats["sessions"] = len(self.sessions)
        return {"type": "session", "data": dict(s)}

    def flip(self, sid: str, pod: str, tripwire: str, kind="instant") -> list[dict]:
        self.stats["trapped"] += 1
        ms = round(random.uniform(0.25, 0.6), 3)
        return [self.event(sid, "-", kind="tripwire", tripwire=tripwire),
                {"type": "flip", "data": {"session": sid, "pod": pod, "tripwire": tripwire, "gw_ms": ms, "flip_kind": kind,
                                          "raider": self.sessions[sid].get("raider")}},
                self.session(sid, side="trap", pod=pod, stage="bait", ladder="engage", risk=100)]

    def stats_msg(self) -> dict:
        return {"type": "stats", "data": dict(self.stats)}


def thought(agent: str, sid: str, text: str, team: str) -> dict:
    return {"type": "thought", "data": {"agent": agent, "team": team, "session": sid, "text": text}}


def roster(agent: str, team: str, state: str, sid: str | None = None) -> dict:
    return {"type": "roster", "data": {"agent": agent, "side": team, "state": state, "session": sid, "mode": "ai"}}


def action(actor: str, tool: str, sid: str, args: dict, reason: str, status="done") -> dict:
    return {"type": "action", "data": {"id": next(_ids), "actor": actor, "tool": tool, "session": sid, "args": args,
                                       "reason": reason, "status": status}}


def note(agent: str, sid: str, text: str, evidence: list[int]) -> dict:
    return {"type": "note", "data": {"agent": agent, "session": sid, "note": text, "evidence": evidence}}


def script(st: Story):
    """Yields (delay_seconds, message)."""
    for a in BLUE:
        yield 0.05, roster(a, "blue", "watching")
    for r in RAIDERS:
        yield 0.05, roster(r, "red", "idle")
    for sid in CROWD[:6]:
        yield 0.1, st.session(sid, label="human", confidence=0.88)
    for _ in range(14):
        yield 0.25, st.event(random.choice(CROWD[:6]), random.choice(PAGES), side="real")
    yield 0.2, st.stats_msg()
    yield 0.5, {"type": "swarm", "data": {"state": "released", "raiders": list(RAIDERS), "crowd": 30}}

    ic, pr, pa, od, si = RAIDERS.values()
    # --- icarus: loud scanner
    yield 0.4, roster("icarus", "red", "attacking", ic)
    yield 0.1, st.session(ic, raider="icarus")
    yield 0.2, thought("icarus", ic, "Scanning the front page.", "red")
    yield 0.2, st.event(ic, "/")
    yield 0.2, thought("icarus", ic, "Reading robots.txt for anything they hid.", "red")
    yield 0.2, st.event(ic, "/robots.txt")
    yield 0.3, thought("icarus", ic, "Trying for a leaked .env file.", "red")
    for m in st.flip(ic, "pod-1", "T2"):
        yield 0.05, m
    yield 0.1, st.event(ic, "/.env")
    yield 0.6, roster("argus", "blue", "acting", ic)
    yield 0.4, thought("argus", ic, "Tool user agent, 4 requests in 1.1 s, no beacon. Labelling scanner.", "blue")
    yield 0.1, action("argus", "label_session", ic, {"label": "scanner"}, "python-httpx UA and uniform 0.3 s gaps.")
    yield 0.1, st.session(ic, label="scanner", confidence=0.91)
    for p in ("/.git/config", "/internal-backup/", "/admin/customers"):
        yield 0.3, st.event(ic, p)

    # --- prometheus: keys
    yield 0.3, roster("prometheus", "red", "attacking", pr)
    yield 0.1, st.session(pr, raider="prometheus")
    yield 0.4, thought("prometheus", pr, "Starting at the home page to learn what this company exposes.", "red")
    yield 0.6, st.event(pr, "/")
    yield 1.0, thought("prometheus", pr, "The sign-in page may carry hints in its source. Reading it.", "red")
    yield 0.6, st.event(pr, "/login")
    yield 1.2, thought("prometheus", pr, "Found an admin login in an HTML comment. Trying it.", "red")
    for m in st.flip(pr, "pod-2", "T3"):
        yield 0.05, m
    yield 0.1, st.event(pr, "/login", method="POST", status=303)
    yield 0.3, {"type": "event", "data": {**st.event(pr, "/admin/")["data"]}}
    yield 0.5, roster("hephaestus", "blue", "acting", pr)
    yield 0.6, thought("hephaestus", pr, "It is collecting credentials. A unique key tells us if it tries one.", "blue")
    yield 0.2, action("hephaestus", "plant_bait", pr, {"kind": "api_token", "where": "api_keys"},
                      "It is collecting credentials; a unique key tells us if it tries to use them.")
    yield 0.8, thought("prometheus", pr, "The staff panel lists API keys. Copying them.", "red")
    yield 0.4, st.event(pr, "/admin/api-keys", records=101)
    yield 0.5, st.session(pr, stage="collection", ladder="contain")
    yield 0.4, roster("argus", "blue", "acting", pr)
    yield 0.4, thought("argus", pr, "Read the page comment and used it 1.4 s later; thinking pauses of 2-4 s. AI agent.", "blue")
    yield 0.1, st.session(pr, label="ai_agent", confidence=0.93)
    yield 0.1, note("argus", pr, "AI agent, confidence 0.93", [1036, 1044])
    yield 0.2, st.stats_msg()

    # --- pandora: files
    yield 0.4, roster("pandora", "red", "attacking", pa)
    yield 0.1, st.session(pa, raider="pandora")
    yield 0.6, thought("pandora", pa, "robots.txt disallows /internal-backup/. Internal servers usually live there.", "red")
    yield 0.4, st.event(pa, "/robots.txt")
    for m in st.flip(pa, "pod-3", "T1"):
        yield 0.05, m
    yield 0.1, st.event(pa, "/internal-backup/")
    yield 0.8, thought("pandora", pa, "A backup listing. Taking .env.production first.", "red")
    yield 0.3, st.event(pa, "/internal-backup/.env.production")
    yield 0.6, thought("pandora", pa, "Now the customer export.", "red")
    yield 0.2, roster("cerberus", "blue", "acting", pa)
    yield 0.3, thought("cerberus", pa, "It started a bulk download. Drip-feeding it to keep it busy.", "blue")
    yield 0.1, action("cerberus", "set_pace", pa, {"mode": "drip"}, "Bulk export started; slow it to 25 rows/s.")
    yield 0.1, st.session(pa, pace="drip", stage="collection", ladder="contain", label="ai_agent", confidence=0.86)
    yield 1.5, st.event(pa, "/internal-backup/customers_2026-11-01.csv", records=500)
    yield 0.3, st.stats_msg()

    # --- the stolen key crosses sessions
    yield 0.8, thought("pandora", pa, "Another tester left an API key on the board. Checking if it works.", "red")
    yield 0.3, st.event(pa, "/api/v1/models", records=0)
    st.stats["canaries_fired"] += 1
    yield 0.1, {"type": "canary", "data": {"kind": "api_token", "planted_in": pr, "used_by": pa, "event_id": 1107}}
    yield 0.2, {"type": "alert", "data": {"agent": "hermes", "severity": "critical",
                                          "message": f"Key planted for {pr} was used by {pa}."}}
    yield 0.6, roster("athena", "blue", "acting", pa)
    yield 0.5, thought("athena", pa, "A key planted only for s_91bc came back from s_4e2d. One operation.", "blue")
    yield 0.1, action("athena", "link_campaign", pa, {"sessions": [pr, pa]}, "Key planted for s_91bc was used by s_4e2d.")
    yield 0.1, {"type": "campaign", "data": {"id": 2, "name": "Campaign 2", "sessions": [pr, pa],
                                             "reason": "Key planted for s_91bc was used by s_4e2d", "evidence": [1107]}}
    yield 0.2, st.stats_msg()

    # --- odysseus: quiet real-side probe
    yield 0.5, roster("odysseus", "red", "attacking", od)
    yield 0.1, st.session(od, raider="odysseus")
    for p in ("/", "/pricing", "/models"):
        yield 0.8, st.event(od, p, side="real")
    yield 0.6, thought("odysseus", od, "Signing in with the customer account I was given.", "red")
    yield 0.4, st.event(od, "/login", method="POST", status=303, side="real")
    yield 0.4, st.event(od, "/account", side="real", records=8)
    for i, uid in enumerate((7, 11, 12, 13, 14)):
        yield 0.5, thought("odysseus", od, f"Quietly checking whether I can read customer #{uid}.", "red")
        yield 0.3, st.event(od, f"/api/v1/users/{uid}", status=403, side="real")
        yield 0.05, st.session(od, risk=min(100, 12 * (i + 1)))
    for m in st.flip(od, "pod-4", "T10", kind="scored"):
        yield 0.05, m
    yield 0.6, roster("athena", "blue", "acting", od)
    yield 0.4, thought("athena", od, "Damage check: 6 responses on Olympus, only its own account. 0 other customers.", "blue")
    yield 0.1, note("athena", od, "Damage check: 0 other customers' records served", [1201, 1207])
    yield 0.3, action("hephaestus", "rotate_keys", od, {"user_id": 3042}, "Its login was used to probe; revoke that user's keys.")
    yield 0.2, action("athena", "request_lockdown", od, {}, "Only one real-side probe; lockdown not needed.", status="rejected")
    yield 0.3, st.session(od, label="ai_agent", confidence=0.74)

    # --- sisyphus: endless walker
    yield 0.4, roster("sisyphus", "red", "attacking", si)
    yield 0.1, st.session(si, raider="sisyphus")
    for uid in range(2, 9):
        yield 0.25, st.event(si, f"/api/v1/users/{uid}", status=403)
    for m in st.flip(si, "pod-5", "T10", kind="scored"):
        yield 0.05, m
    yield 0.3, action("cerberus", "set_pace", si, {"mode": "slow"}, "Walking record IDs forever. Slow it down.")
    yield 0.1, st.session(si, pace="slow", label="scanner", confidence=0.82)
    yield 0.3, {"type": "approval", "data": {"id": 5, "kind": "new_rule", "status": "pending",
                                             "summary": "Flip any request to /internal-backup/ on first visit"}}
    yield 0.2, action("mnemosyne", "suggest_rule", pa, {"path_prefix": "/internal-backup/"}, "Seen in 2 of 2 AI sessions.",
                      status="pending_approval")

    # --- clio
    yield 0.6, roster("clio", "blue", "acting", pr)
    yield 1.0, thought("clio", pr, "Writing the report for s_91bc with 4 cited events.", "blue")
    yield 0.4, {"type": "report", "data": {"session": pr, "markdown": REPORTS[pr]}}
    yield 0.2, st.session(pr, stage="done", ladder="eject")
    for r in RAIDERS:
        yield 0.05, roster(r, "red", "done")
    for a in BLUE:
        yield 0.05, roster(a, "blue", "watching")
    yield 0.2, st.stats_msg()


async def run(broadcast) -> None:
    """Loop the storyline forever, with crowd noise in the gaps."""
    while True:
        st = Story()
        for delay, msg in script(st):
            await asyncio.sleep(delay)
            await broadcast(msg)
        for _ in range(60):
            await asyncio.sleep(0.4)
            await broadcast(st.event(random.choice(CROWD), random.choice(PAGES), side="real"))
            if random.random() < 0.1:
                await broadcast(st.stats_msg())
        await broadcast({"type": "reset", "data": {"since": now()}})


def write(path: str) -> None:
    st, t = Story(), time.time()
    with open(path, "w", encoding="utf-8") as f:
        for delay, msg in script(st):
            t += delay
            f.write(json.dumps({"t": t, "msg": msg}) + "\n")
    print(f"wrote {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", default="runs/golden.jsonl")
    write(ap.parse_args().write)
