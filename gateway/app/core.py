"""Charon's shared state and routing decisions.

`Gateway` holds every in-memory component and implements the hard rules
R1-R6. Both the public handler and the admin API go through it, so the rules
can't be bypassed from either side.
"""

from __future__ import annotations

import asyncio
import logging
import time
from ipaddress import ip_address

import httpx
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .canaries import Canary, CanaryRegistry
from .config import Settings
from .events import EventWriter
from .lockdown import Lockdown
from .pods import PodPool
from .rules import DynamicRule
from .sessions import Session, SessionStore

log = logging.getLogger("gateway.core")


class RuleError(Exception):
    """A request that would break a hard routing rule."""


class Gateway:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = SessionStore()
        self.canaries = CanaryRegistry()
        self.pods = PodPool(settings.pods)
        self.writer = EventWriter(settings.events_db_url, self.store)
        self.lockdown = Lockdown(self._on_lockdown)
        self.rules: list[DynamicRule] = []
        self.known_attackers: list[dict] = []
        self.enabled_upstreams = set(settings.real_upstreams)
        self._rr = 0
        self._auth = URLSafeTimedSerializer(settings.session_secret, salt="hl-auth")
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0), follow_redirects=False,
                                        limits=httpx.Limits(max_connections=400, max_keepalive_connections=100))

    # ---- lifecycle -------------------------------------------------------
    async def start(self) -> None:
        sessions, canaries = await self.writer.load_state()
        for s in sessions:
            self.store.load(s)
            if s.pod:
                self.pods.attach(s.pod, s.session_id)
        for c in canaries:
            self.canaries.by_value[c.value] = c
        asyncio.create_task(self.writer.run())
        asyncio.create_task(self._housekeeping())
        log.info("gateway started with %d live sessions, %d canaries", len(sessions), len(canaries))

    async def _housekeeping(self) -> None:
        while True:
            await asyncio.sleep(5)
            try:
                await self._expire_idle_sessions()
                await self._check_pods()
                self.known_attackers = await self.writer.fingerprints()
                self.rules = [r for r in self.rules if r.expires > time.time()]
            except Exception:  # keep the loop alive no matter what
                log.exception("housekeeping failed")

    async def _expire_idle_sessions(self) -> None:
        cutoff = time.time() - self.settings.pod_idle_reset_min * 60
        for s in self.store.active():
            if s.last_seen < cutoff:
                s.ended = True
                s.advance_stage("done")
                self.store.touch(s)
                if s.pod and self.pods.release(s.pod, s.session_id):
                    await self.reset_pod(s.pod)

    async def _check_pods(self) -> None:
        for pod in self.pods.pods.values():
            try:
                r = await self.client.get(f"http://{pod.name}:{self.settings.upstream_port}/_edge/health", timeout=2.0)
                pod.healthy = r.status_code == 200
            except httpx.HTTPError:
                pod.healthy = False

    # ---- routing ---------------------------------------------------------
    def real_upstream(self) -> str:
        live = [u for u in self.settings.real_upstreams if u in self.enabled_upstreams] or self.settings.real_upstreams
        self._rr = (self._rr + 1) % len(live)
        return live[self._rr]

    def upstream_for(self, session: Session) -> str:
        return session.pod if session.trapped and session.pod else self.real_upstream()

    def flip(self, session: Session, tripwire: str, kind: str, gw_ms: float, now: float) -> None:
        """Move a session into Tartarus. Instant flips are permanent (R1)."""
        if session.trapped:
            return
        pod, shared = self.pods.assign(session.session_id)
        session.side, session.pod = "trap", pod
        session.flipped_by, session.flip_kind = tripwire, kind
        session.ladder = "engage"
        session.advance_stage("bait")
        session.pace_count = 0
        self.store.touch(session)
        self.writer.emit("flip", session.session_id, side="trap", pod=pod, tripwire=tripwire, gw_ms=gw_ms,
                         src_ip=session.src_ip or None,
                         payload={"gw_ms": round(gw_ms, 3), "flip_kind": kind, "pod": pod, "raider": session.raider})
        if shared:
            self.writer.emit("pod_shared", pod=pod, payload={"pod": pod, "session": session.session_id})

    def lockdown_allows_real(self, session: Session, cookies: dict[str, str]) -> bool:
        """R4: during lockdown only known humans with a valid login and low risk reach Olympus."""
        if session.label != "human" or session.decayed_risk(time.time()) >= 30:
            return False
        try:
            self._auth.loads(cookies.get("hl_auth", ""), max_age=7 * 24 * 3600)
            return True
        except BadSignature:
            return False

    def matches_known_attacker(self, session: Session) -> bool:
        """R6: a returning fingerprint is trapped on its first request."""
        return any(
            a["user_agent"] == session.user_agent and a["src_ip"] == session.src_ip
            for a in self.known_attackers
        )

    def is_edge(self, ip: str) -> bool:
        try:
            return ip_address(ip) in self.settings.edge_subnet
        except ValueError:
            return False

    # ---- admin operations (all enforce the hard rules) --------------------
    async def route(self, session: Session, side: str, reason: str, approval_id: int | None) -> None:
        if side == "trap":
            self.flip(session, "blue", "blue", 0.0, time.time())
            return
        if side != "real":
            raise RuleError("side must be trap or real")
        if session.flip_kind in ("instant", "fingerprint"):
            raise RuleError("R1: trapped sessions cannot return to the real side")
        if approval_id is None or not await self.writer.approval_ok(approval_id, "release", session.session_id):
            raise RuleError("R2: release needs a Zeus approval for this session")
        if session.pod:
            self.pods.release(session.pod, session.session_id)
        session.side, session.pod, session.ladder = "real", None, "watch"
        self.store.touch(session)

    def block(self, session: Session) -> None:
        if not session.pod:
            session.pod, _ = self.pods.assign(session.session_id)
        session.side, session.ladder = "blocked", "eject"
        self.store.touch(session)

    def register_canary(self, canary: Canary) -> None:
        if self.canaries.register(canary):
            self.writer.canaries.append(canary)

    async def reset_pod(self, pod: str) -> bool:
        try:
            r = await self.client.post(f"http://{pod}:{self.settings.upstream_port}/_edge/reset", timeout=10.0)
            ok = r.status_code == 200
        except httpx.HTTPError:
            ok = False
        self.writer.emit("pod_reset", pod=pod, payload={"pod": pod, "ok": ok})
        return ok

    async def reset_all(self) -> int:
        """Reset Tartarus: end every session, clear and reset every pod."""
        ended = self.store.end_all()
        self.pods.clear()
        await asyncio.gather(*(self.reset_pod(p) for p in self.pods.pods))
        return len(ended)

    def _on_lockdown(self, state: str, info: dict) -> None:
        self.writer.emit("lockdown", payload={"state": state, **info})
