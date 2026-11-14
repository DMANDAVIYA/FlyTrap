"""dash-api: snapshot API, live WebSocket feed, run recording and replay, button proxy.

LISTENs on events_new, maps new rows to WebSocket messages (plan 6.8),
broadcasts them, and records every message to runs/<run_id>.jsonl.
MOCK=1 runs the scripted storyline from mock_feed.py instead (no database needed).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncpg
import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import mock_feed
from mapping import to_messages

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("dash-api")

DSN = os.getenv("EVENTS_DB_URL", "")
CONTROLLER = os.getenv("CONTROLLER_URL", "http://controller:8070")
RUNS = Path(os.getenv("RUNS_DIR", Path(__file__).resolve().parent / "runs"))
MOCK = os.getenv("MOCK", "0") == "1" or not DSN
RUNS.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="flytrap-dash-api", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---- clients, broadcast, recording ------------------------------------------
class Client:
    def __init__(self, ws: WebSocket) -> None:
        self.ws, self.id = ws, uuid.uuid4().hex[:8]
        self.replay: asyncio.Task | None = None


class Hub:
    def __init__(self) -> None:
        self.clients: dict[str, Client] = {}
        self.recent: deque[dict] = deque(maxlen=400)   # for /api/state in mock mode and late joiners
        self.run_id = ""
        self.run_file = None
        self.new_run()

    def new_run(self, label: str = "run") -> None:
        if self.run_file:
            self.run_file.close()
        self.run_id = f"{label}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.run_file = open(RUNS / f"{self.run_id}.jsonl", "a", encoding="utf-8")

    async def broadcast(self, msg: dict) -> None:
        self.recent.append(msg)
        if self.run_file and msg.get("type") != "hello":
            self.run_file.write(json.dumps({"t": time.time(), "msg": msg}, default=str) + "\n")
            self.run_file.flush()
        text = json.dumps(msg, default=str)
        for c in list(self.clients.values()):
            if c.replay and not c.replay.done():
                continue
            try:
                await c.ws.send_text(text)
            except Exception:
                self.clients.pop(c.id, None)


hub = Hub()
state = {"since": datetime.now(timezone.utc) - timedelta(hours=6), "lockdown": {"state": "off"}, "pool": None}


# ---- live feed from events-db ---------------------------------------------------
async def connect_pool() -> asyncpg.Pool:
    while True:
        try:
            return await asyncpg.create_pool(DSN, min_size=1, max_size=5)
        except (OSError, asyncpg.PostgresError) as exc:
            log.warning("events-db not ready (%s), retrying", exc)
            await asyncio.sleep(2)


async def live_feed(pool: asyncpg.Pool) -> None:
    wake = asyncio.Event()
    last_id = int(await pool.fetchval("SELECT COALESCE(max(id), 0) FROM events"))
    while True:
        try:
            conn = await asyncpg.connect(DSN)
            await conn.add_listener("events_new", lambda *_: wake.set())
            log.info("listening on events_new from id %d", last_id)
            while not conn.is_closed():
                try:
                    await asyncio.wait_for(wake.wait(), timeout=2.0)   # poll anyway, in case a NOTIFY was missed
                except asyncio.TimeoutError:
                    pass
                wake.clear()
                rows = await pool.fetch(
                    "SELECT id, ts, session_id, kind, side, pod, method, path, status, tripwire, records, payload, gw_ms "
                    "FROM events WHERE id > $1 ORDER BY id LIMIT 1000", last_id)
                for row in rows:
                    last_id = max(last_id, row["id"])
                    for msg in to_messages(row):
                        if msg["type"] == "lockdown":
                            state["lockdown"] = msg["data"]
                        await hub.broadcast(msg)
        except (OSError, asyncpg.PostgresError) as exc:
            log.warning("feed connection lost (%s); reconnecting", exc)
            await asyncio.sleep(2)


SESSIONS_SQL = """
SELECT session_id, side, pod, label, confidence, stage, ladder, risk, pace, raider, flipped_by, flip_kind, ended,
       left(user_agent, 120) AS user_agent, last_seen, first_seen, reasons
FROM sessions WHERE last_seen > $1 ORDER BY last_seen DESC LIMIT $2
"""


def session_msg(r) -> dict:
    reasons = r["reasons"]
    if isinstance(reasons, str):
        try:
            reasons = json.loads(reasons)
        except ValueError:
            reasons = None
    return {"session": r["session_id"], "side": r["side"], "pod": r["pod"], "label": r["label"],
            "confidence": r["confidence"], "stage": r["stage"], "ladder": r["ladder"], "risk": r["risk"],
            "pace": r["pace"], "raider": r["raider"], "flipped_by": r["flipped_by"], "flip_kind": r["flip_kind"],
            "ended": r["ended"], "user_agent": r["user_agent"], "reasons": reasons,
            "last_seen": r["last_seen"].isoformat(), "first_seen": r["first_seen"].isoformat()}


async def compute_stats(pool: asyncpg.Pool) -> dict:
    since = state["since"]
    async with pool.acquire() as conn:
        taken = await conn.fetchval(r"""
            SELECT COALESCE(sum(CASE WHEN rec ~ ':\d+-\d+$'
              THEN split_part(split_part(rec, ':', 2), '-', 2)::int - split_part(split_part(rec, ':', 2), '-', 1)::int + 1
              ELSE 1 END), 0)
            FROM events, unnest(records) rec
            WHERE ts > $1 AND kind = 'request' AND side IN ('trap', 'blocked')""", since)
        real_rows = await conn.fetch("""
            SELECT e.session_id, rec FROM events e JOIN sessions s USING (session_id), unnest(e.records) rec
            WHERE e.ts > $1 AND e.kind = 'request' AND e.side = 'real' AND s.side IN ('trap', 'blocked')""", since)
        trapped = await conn.fetchval(
            "SELECT count(*) FROM sessions WHERE side IN ('trap', 'blocked') AND NOT ended AND last_seen > $1", since)
        fired = await conn.fetchval("SELECT count(*) FROM canaries WHERE fired_at > $1", since)
        flip_ms = await conn.fetchval("SELECT avg(gw_ms) FROM events WHERE ts > $1 AND kind = 'flip' AND gw_ms > 0", since)
        sessions = await conn.fetchval("SELECT count(*) FROM sessions WHERE last_seen > $1", since)
        req_ms = await conn.fetchrow(
            "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY gw_ms) AS p50, "
            "percentile_cont(0.95) WITHIN GROUP (ORDER BY gw_ms) AS p95 "
            "FROM events WHERE ts > now() - interval '5 minutes' AND kind = 'request'")
        try:   # TimescaleDB continuous aggregate (requests per minute by side)
            buckets = await conn.fetch(
                "SELECT bucket, side, sum(n)::int AS n FROM stats_1m WHERE bucket > now() - interval '15 minutes' "
                "AND kind = 'request' GROUP BY bucket, side ORDER BY bucket")
        except asyncpg.PostgresError:
            buckets = []
    # Damage check: other customers' records served on the real side to sessions that ended up trapped.
    own: dict[str, dict[str, int]] = {}
    for r in real_rows:
        if r["rec"].startswith("user:"):
            own.setdefault(r["session_id"], {}).setdefault(r["rec"], 0)
            own[r["session_id"]][r["rec"]] += 1
    exposed = 0
    for recs in own.values():
        mine = max(recs, key=recs.get)
        exposed += sum(1 for rec in recs if rec != mine)
    per_min: dict[str, dict[str, int]] = {}
    for b in buckets:
        per_min.setdefault(b["bucket"].isoformat(), {})[b["side"] or "-"] = b["n"]
    return {"real_records_exposed": exposed, "fake_records_taken": int(taken or 0), "trapped": int(trapped or 0),
            "canaries_fired": int(fired or 0), "avg_flip_ms": round(float(flip_ms), 3) if flip_ms else None,
            "sessions": int(sessions or 0),
            "gw_p50_ms": round(req_ms["p50"], 3) if req_ms and req_ms["p50"] is not None else None,
            "gw_p95_ms": round(req_ms["p95"], 3) if req_ms and req_ms["p95"] is not None else None,
            "per_minute": [{"bucket": k, **v} for k, v in per_min.items()]}


async def pollers(pool: asyncpg.Pool) -> None:
    cache: dict[str, tuple] = {}
    tick = 0
    while True:
        await asyncio.sleep(1)
        tick += 1
        try:
            rows = await pool.fetch(SESSIONS_SQL, datetime.now(timezone.utc) - timedelta(minutes=30), 300)
            for r in rows:
                m = session_msg(r)
                key = (m["side"], m["label"], m["stage"], m["ladder"], m["risk"], m["pace"], m["ended"], m["confidence"],
                       m["pod"])
                if cache.get(m["session"]) != key:
                    cache[m["session"]] = key
                    await hub.broadcast({"type": "session", "data": m})
            if tick % 2 == 0:
                await hub.broadcast({"type": "stats", "data": await compute_stats(pool)})
        except (OSError, asyncpg.PostgresError) as exc:
            log.warning("poll failed: %s", exc)


@app.on_event("startup")
async def startup() -> None:
    if MOCK:
        log.info("MOCK mode: scripted storyline, no database")
        asyncio.create_task(mock_feed.run(hub.broadcast))
        return
    pool = await connect_pool()
    state["pool"] = pool
    row = await pool.fetchrow("SELECT payload FROM events WHERE kind = 'lockdown' ORDER BY id DESC LIMIT 1")
    if row and row["payload"]:
        state["lockdown"] = json.loads(row["payload"])
    asyncio.create_task(live_feed(pool))
    asyncio.create_task(pollers(pool))


# ---- HTTP -----------------------------------------------------------------------
async def controller(method: str, path: str, body: dict | None = None, timeout: float = 15.0) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as c:
        try:
            r = await c.request(method, f"{CONTROLLER}{path}", json=body)
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"controller unreachable: {exc}") from exc
    try:
        return r.json()
    except ValueError:
        return {"ok": r.status_code < 300, "status": r.status_code}


@app.get("/healthz")
async def healthz():
    return {"ok": True, "mock": MOCK, "clients": len(hub.clients), "run": hub.run_id}


@app.get("/api/state")
async def snapshot():
    pool: asyncpg.Pool | None = state["pool"]
    if MOCK or pool is None:
        return {"mock": True, "messages": list(hub.recent), "lockdown": state["lockdown"], "run": hub.run_id}
    # Story events (thoughts, flips, actions...) and plain requests are fetched separately,
    # so crowd traffic can't push the story out of the snapshot.
    cols = "SELECT id, ts, session_id, kind, side, pod, method, path, status, tripwire, records, payload, gw_ms FROM events "
    story = await pool.fetch(cols + "WHERE ts > $1 AND kind NOT IN ('request', 'beacon') ORDER BY id DESC LIMIT 600",
                             state["since"])
    plain = await pool.fetch(cols + "WHERE ts > $1 AND kind = 'request' ORDER BY id DESC LIMIT 200", state["since"])
    rows = sorted([*story, *plain], key=lambda r: r["id"])
    messages = [m for r in rows for m in to_messages(r)]
    sessions = await pool.fetch(SESSIONS_SQL, max(state["since"], datetime.now(timezone.utc) - timedelta(minutes=30)), 200)
    approvals = await pool.fetch("SELECT id, kind, summary, status, ts FROM approvals WHERE status = 'pending' ORDER BY id")
    campaigns = await pool.fetch("SELECT id, name, session_ids, reason, evidence FROM campaigns WHERE created_at > $1 "
                                 "ORDER BY id", state["since"])
    reports = await pool.fetch("SELECT session_id, created_at FROM reports WHERE created_at > $1 ORDER BY created_at DESC",
                               state["since"])
    roster = await pool.fetch(
        "SELECT DISTINCT ON (payload->>'agent') payload FROM events WHERE kind = 'roster' AND ts > now() - interval '2 hours' "
        "ORDER BY payload->>'agent', id DESC")
    try:
        health = await controller("GET", "/health", timeout=2.0)
    except HTTPException:
        health = {"ok": False}
    return {
        "mock": False, "run": hub.run_id, "messages": messages,
        "sessions": [session_msg(r) for r in sessions],
        "stats": await compute_stats(pool),
        "approvals": [{**dict(a), "ts": a["ts"].isoformat()} for a in approvals],
        "campaigns": [{"id": c["id"], "name": c["name"], "sessions": c["session_ids"], "reason": c["reason"],
                       "evidence": c["evidence"]} for c in campaigns],
        "reports": [{"session": r["session_id"], "created_at": r["created_at"].isoformat()} for r in reports],
        "roster": [json.loads(r["payload"]) for r in roster],
        "lockdown": state["lockdown"], "controller": health,
    }


@app.get("/api/sessions/{sid}")
async def session_detail(sid: str):
    pool: asyncpg.Pool | None = state["pool"]
    if pool is None:
        raise HTTPException(404)
    row = await pool.fetchrow(SESSIONS_SQL.replace("WHERE last_seen > $1 ORDER BY last_seen DESC LIMIT $2",
                                                   "WHERE session_id = $1"), sid)
    if not row:
        raise HTTPException(404, "no such session")
    events = await pool.fetch(
        "SELECT id, ts, session_id, kind, side, pod, method, path, status, tripwire, records, payload, gw_ms "
        "FROM events WHERE session_id = $1 ORDER BY id DESC LIMIT 300", sid)
    notes = await pool.fetch("SELECT ts, agent, note, evidence FROM agent_notes WHERE session_id = $1 ORDER BY id", sid)
    actions = await pool.fetch("SELECT id, ts, actor, tool, args, reason, status FROM actions WHERE session_id = $1 ORDER BY id", sid)
    report = await pool.fetchrow("SELECT markdown FROM reports WHERE session_id = $1", sid)
    return {"session": session_msg(row), "messages": [m for r in reversed(events) for m in to_messages(r)],
            "notes": [{**dict(n), "ts": n["ts"].isoformat()} for n in notes],
            "actions": [{**dict(a), "ts": a["ts"].isoformat(), "args": json.loads(a["args"]) if a["args"] else {}}
                        for a in actions],
            "report": report["markdown"] if report else None}


@app.get("/api/reports/{sid}")
async def report(sid: str):
    pool: asyncpg.Pool | None = state["pool"]
    if MOCK or pool is None:
        md = mock_feed.REPORTS.get(sid)
        if not md:
            raise HTTPException(404)
        return {"session": sid, "markdown": md}
    row = await pool.fetchrow("SELECT markdown, report FROM reports WHERE session_id = $1", sid)
    if not row:
        raise HTTPException(404, "no report yet")
    return {"session": sid, "markdown": row["markdown"], "report": json.loads(row["report"])}


@app.get("/api/runs")
async def runs():
    files = sorted(RUNS.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return {"runs": [{"run": f.stem, "bytes": f.stat().st_size, "current": f.stem == hub.run_id}
                     for f in files if f.stat().st_size > 0]}


def load_run(run: str) -> list[dict]:
    path = (RUNS / f"{Path(run).name}.jsonl")
    if not path.exists():
        raise HTTPException(404, "no such run")
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            lines.append(json.loads(line))
        except ValueError:
            continue
    return lines


async def play(client: Client, run: str, speed: float) -> None:
    lines = load_run(run)
    await client.ws.send_text(json.dumps({"type": "replay", "data": {"state": "start", "run": run, "speed": speed,
                                                                    "messages": len(lines)}}))
    prev = lines[0]["t"] if lines else 0
    for item in lines:
        await asyncio.sleep(min(max(item["t"] - prev, 0) / speed, 5.0))
        prev = item["t"]
        await client.ws.send_text(json.dumps(item["msg"], default=str))
    await client.ws.send_text(json.dumps({"type": "replay", "data": {"state": "end", "run": run}}))


def start_replay(client: Client, run: str, speed: float) -> None:
    load_run(run)  # 404 early
    if client.replay and not client.replay.done():
        client.replay.cancel()
    client.replay = asyncio.create_task(play(client, run, max(0.25, min(speed, 16.0))))


@app.get("/api/replay")
async def replay(run: str, speed: float = 1.0, client: str = ""):
    """Switch one dashboard socket into replay (client id comes from the socket's hello message)."""
    c = hub.clients.get(client)
    if not c:
        return {"ok": True, "run": run, "messages": [line["msg"] for line in load_run(run)]}
    start_replay(c, run, speed)
    return {"ok": True, "run": run, "speed": speed}


CONTROL = {
    "release": ("POST", "/swarm/release"),
    "stop": ("POST", "/swarm/stop"),
    "reset": ("POST", "/swarm/reset"),
}


@app.post("/api/control/{action}")
async def control(action: str, body: dict | None = None):
    body = body or {}
    if action in CONTROL:
        method, path = CONTROL[action]
        if action == "release":
            hub.new_run("run")
            body = {"raiders": body.get("raiders") or ["prometheus", "pandora", "odysseus", "icarus", "sisyphus"],
                    "crowd": body.get("crowd", 30), "drones": body.get("drones", 0),
                    "demo_mode": body.get("demo_mode", True)}
        if action == "reset":
            state["since"] = datetime.now(timezone.utc)
            await hub.broadcast({"type": "reset", "data": {"since": state["since"].isoformat()}})
        if MOCK:
            return {"ok": True, "mock": True}
        return await controller(method, path, body if action == "release" else None, timeout=30.0)
    if MOCK:
        return {"ok": True, "mock": True}
    reason = body.get("reason") or "Zeus pressed the button on the console"
    if action == "lockdown":
        return await controller("POST", "/tools/request_lockdown", {"agent": "zeus", "reason": reason, "args": {"reason": reason}})
    if action == "cancel":
        return await controller("POST", "/tools/cancel_lockdown", {"agent": "zeus", "reason": reason, "args": {"reason": reason}})
    if action in ("approve", "reject"):
        if "id" not in body:
            raise HTTPException(400, "id required")
        return await controller("POST", f"/approvals/{int(body['id'])}", {"decision": action, "by": "zeus"})
    if action == "report":
        return await controller("POST", f"/reports/{body.get('session', '')}", timeout=60.0)
    if action == "raider":
        return await controller("POST", f"/raiders/{body.get('name', '')}/start", {"mode": body.get("mode")})
    raise HTTPException(404, "unknown action")


# ---- WebSocket --------------------------------------------------------------------
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    client = Client(websocket)
    hub.clients[client.id] = client
    await websocket.send_text(json.dumps({"type": "hello", "data": {"client": client.id, "mock": MOCK, "run": hub.run_id}}))
    try:
        while True:
            msg = json.loads(await websocket.receive_text())
            if msg.get("type") == "replay":
                try:
                    start_replay(client, str(msg.get("run", "golden")), float(msg.get("speed", 1)))
                except HTTPException:
                    await websocket.send_text(json.dumps({"type": "replay", "data": {"state": "error"}}))
            elif msg.get("type") == "live" and client.replay:
                client.replay.cancel()
                await websocket.send_text(json.dumps({"type": "replay", "data": {"state": "end"}}))
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass
    finally:
        if client.replay:
            client.replay.cancel()
        hub.clients.pop(client.id, None)
