"""The public catch-all handler: identify, judge, route, forward, record."""

from __future__ import annotations

import asyncio
import json
import random
import time

import httpx
from fastapi import Request
from fastapi.responses import Response, StreamingResponse

from . import proxy, rules
from .canaries import Canary, count_records, parse_bait_header, parse_records_header
from .core import Gateway
from .sessions import COOKIE, Session

INTERNAL_PATHS = ("/_edge", "/_admin")
COOKIE_MAX_AGE = 30 * 24 * 3600


def _body_worth_reading(request: Request, limit: int) -> bool:
    length = request.headers.get("content-length")
    return request.method in ("POST", "PUT", "PATCH") and length is not None and length.isdigit() and int(length) <= limit


async def handle(gw: Gateway, request: Request) -> Response:
    started = time.perf_counter()
    now = time.time()
    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")
    session, set_cookie = gw.store.resolve(request.cookies.get(COOKIE), ip, ua)
    session.last_seen = now
    raider = request.headers.get("x-raider")
    if raider and gw.is_edge(ip) and session.raider != raider:
        session.raider = raider[:32]
    gw.store.touch(session)

    path, query = request.url.path, request.url.query
    body = await request.body() if _body_worth_reading(request, gw.settings.max_body_scan) else None
    headers_blob = "\n".join(f"{k}: {v}" for k, v in request.headers.items() if k.lower() not in ("cookie",))
    view = rules.RequestView(request.method, path, query, ua, body or b"", headers_blob)

    hits = _judge(gw, session, view, now)
    gw_ms = (time.perf_counter() - started) * 1000
    _apply_hits(gw, session, hits, gw_ms, now)
    if not session.trapped and gw.lockdown.active and not gw.lockdown_allows_real(session, request.cookies):
        gw.flip(session, "lockdown", "lockdown", gw_ms, now)
    beacon = _beacon_payload(body) if path == "/_hl/px" else None

    if path.startswith(INTERNAL_PATHS):  # R5: internal endpoints never reachable from outside
        path = "/__not_found__"
    upstream = gw.upstream_for(session)
    if session.pod:
        gw.pods.touch(session.pod)
    await _pace(session)

    extra = _internal_headers(session, upstream)
    public_base = f"{request.url.scheme}://{request.headers.get('host', 'localhost')}"
    upstream_base = f"http://{upstream}:{gw.settings.upstream_port}"
    url = f"{upstream_base}{path}" + (f"?{query}" if query else "")
    send_body = body if body is not None else request.stream()
    try:
        upstream_resp = await proxy.open_upstream(gw.client, request.method, url,
                                                  proxy.request_headers(request.headers.items(), request.headers.get("host", "localhost"), extra),
                                                  send_body)
    except httpx.HTTPError:
        _record(gw, session, request, path, query, 502, len(body or b""), 0, started, gw_ms, [], upstream, beacon)
        return Response("Bad gateway", status_code=502)

    visible, internal = proxy.response_headers(upstream_resp.headers, public_base, upstream_base)
    records = parse_records_header(internal.get("x-edge-records", ""))
    for kind, value in parse_bait_header(internal.get("x-edge-bait", "")):
        gw.register_canary(Canary(value, kind, session.session_id, path))
    _after_response(gw, session, path, request.method, upstream_resp.status_code,
                    "; ".join(v for k, v in visible if k.lower() == "set-cookie"), now)

    if set_cookie:
        visible.append(("set-cookie", f"{COOKIE}={session.session_id}; Path=/; Max-Age={COOKIE_MAX_AGE}; HttpOnly; SameSite=Lax"))

    req_bytes = len(body or b"")

    async def stream():
        sent = 0
        try:
            async for chunk in upstream_resp.aiter_raw():
                sent += len(chunk)
                yield chunk
        finally:
            await upstream_resp.aclose()
            _record(gw, session, request, path, query, upstream_resp.status_code, req_bytes, sent, started, gw_ms,
                    records, upstream, beacon)

    response = StreamingResponse(stream(), status_code=upstream_resp.status_code)
    response.raw_headers = [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in visible]
    return response


def _judge(gw: Gateway, session: Session, view: rules.RequestView, now: float) -> list[rules.Hit]:
    if session.side == "blocked":
        return []
    hits = rules.instant_hits(view)
    hits += rules.dynamic_hits(view, session, gw.rules, now)
    if not session.trapped and gw.matches_known_attacker(session):
        hits.append(rules.Hit("R6", True, detail="known attacker fingerprint"))
    scan_text = f"{view.path}?{view.query}\n{view.headers_blob}\n{view.body[:16384].decode('utf-8', 'ignore')}"
    for firing in gw.canaries.scan(scan_text, session.session_id):
        hits.append(rules.Hit("T6", True, detail=f"canary {firing.canary.kind} used"))
        gw.writer.fired.append((firing.canary.value, session.session_id))
        gw.writer.emit("canary", session.session_id, side=session.side, pod=session.pod, path=view.path,
                       payload={"kind": firing.canary.kind, "planted_in": firing.canary.session_id,
                                "used_by": session.session_id, "location": firing.canary.location})
        session.advance_stage("exfil")
    hits += rules.scored_hits(view, session, now)
    return hits


def _apply_hits(gw: Gateway, session: Session, hits: list[rules.Hit], gw_ms: float, now: float) -> None:
    for hit in hits:
        risk = session.risk if hit.instant else session.add_risk(hit.score, now)
        gw.writer.emit("tripwire", session.session_id, side=session.side, pod=session.pod, tripwire=hit.tripwire,
                       payload={"score": hit.score, "instant": hit.instant, "risk": risk, "detail": hit.detail})
        if session.trapped:
            continue
        if hit.instant:
            kind = "fingerprint" if hit.tripwire == "R6" else "instant"
            gw.flip(session, hit.tripwire, kind, gw_ms, now)
        elif session.risk >= gw.settings.risk_flip:
            gw.flip(session, hit.tripwire, "scored", gw_ms, now)


def _beacon_payload(body: bytes | None) -> dict:
    try:
        data = json.loads(body or b"{}")
    except ValueError:
        return {}
    return {k: int(data[k]) for k in ("mouse", "keys", "js") if isinstance(data.get(k), (int, float))}


def _after_response(gw: Gateway, session: Session, path: str, method: str, status: int, set_cookie: str, now: float) -> None:
    hit = rules.not_found_hit(session, status, now)
    if hit:
        _apply_hits(gw, session, [hit], 0.0, now)
    if session.trapped:
        stage = rules.infer_stage(path, method, set_cookie, status)
        if stage and session.advance_stage(stage):
            session.ladder = "contain" if stage in ("collection", "exfil") else session.ladder
            gw.store.touch(session)


async def _pace(session: Session) -> None:
    if session.side != "trap" or session.pace != "slow":
        return
    session.pace_count = min(session.pace_count + 1, 10)
    ramp = session.pace_count / 10
    await asyncio.sleep(random.uniform(0.15, 0.6) * ramp)


def _internal_headers(session: Session, upstream: str) -> dict[str, str]:
    headers = {"x-edge-session": session.session_id}
    if session.trapped:
        headers["x-edge-pod"] = upstream
        headers["x-edge-pace"] = session.pace
        headers["x-edge-drip-rate"] = str(session.drip_rate)
    if session.side == "blocked":
        headers["x-edge-block"] = "1"
    return headers


def _record(gw: Gateway, session: Session, request: Request, path: str, query: str, status: int, req_bytes: int,
            resp_bytes: int, started: float, gw_ms: float, records: list[str], upstream: str,
            beacon: dict | None) -> None:
    payload: dict = {"upstream": upstream}
    if session.raider:
        payload["raider"] = session.raider
    if records:
        payload["record_count"] = count_records(records)
    if beacon is not None:
        payload.update(beacon)
    gw.writer.emit(
        "beacon" if beacon is not None else "request", session.session_id,
        side=session.side, pod=session.pod if session.trapped else None, src_ip=session.src_ip or None,
        method=request.method, path=path[:512], query=query[:512] or None, status=status, req_bytes=req_bytes,
        resp_bytes=resp_bytes, latency_ms=round((time.perf_counter() - started) * 1000, 2), gw_ms=round(gw_ms, 3),
        user_agent=session.user_agent[:300], records=records or None, payload=payload,
    )
