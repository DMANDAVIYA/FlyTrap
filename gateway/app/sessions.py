"""Visitor sessions: identity, risk, behaviour windows.

The gateway is the single writer of session state. Everything here is
in-memory and fast; `store.dirty` tells the event writer what to persist.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from collections import deque
from dataclasses import dataclass, field

COOKIE = "hl_sid"
STAGES = ["recon", "bait", "access", "discovery", "collection", "exfil", "done"]


def new_session_id() -> str:
    return "s_" + secrets.token_hex(8)


def fingerprint(ip: str, user_agent: str) -> str:
    return hashlib.sha256(f"{ip}|{user_agent}".encode()).hexdigest()[:16]


@dataclass
class Session:
    session_id: str
    fingerprint: str
    src_ip: str
    user_agent: str
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    side: str = "real"            # real | trap | blocked
    pod: str | None = None
    flipped_by: str | None = None
    flip_kind: str | None = None  # instant | scored | blue | fingerprint | lockdown
    risk: int = 0
    risk_ts: float = field(default_factory=time.time)
    pace: str = "normal"
    drip_rate: int = 2
    pace_count: int = 0
    label: str = "unknown"
    confidence: float | None = None
    reasons: list | None = None
    stage: str = "recon"
    ladder: str = "watch"
    raider: str | None = None
    ended: bool = False
    hits: deque = field(default_factory=lambda: deque(maxlen=200))       # request timestamps
    not_found: deque = field(default_factory=lambda: deque(maxlen=50))   # 404 timestamps
    ids_seen: deque = field(default_factory=lambda: deque(maxlen=50))    # (ts, id) on enumerable APIs

    @property
    def trapped(self) -> bool:
        return self.side in ("trap", "blocked")

    def decayed_risk(self, now: float) -> int:
        """Risk decays 1 point per 10 s since the last change."""
        steps = int(max(0.0, now - self.risk_ts) // 10)
        if steps:
            self.risk = max(0, self.risk - steps)
            self.risk_ts += steps * 10
        return self.risk

    def add_risk(self, points: int, now: float) -> int:
        self.decayed_risk(now)
        self.risk = min(100, self.risk + points)
        self.risk_ts = now
        return self.risk

    def advance_stage(self, stage: str) -> bool:
        if STAGES.index(stage) > STAGES.index(self.stage):
            self.stage = stage
            return True
        return False

    def row(self) -> dict:
        return {
            "session_id": self.session_id, "first_seen": self.first_seen, "last_seen": self.last_seen,
            "fingerprint": self.fingerprint, "src_ip": self.src_ip, "user_agent": self.user_agent[:300],
            "side": self.side, "pod": self.pod, "flipped_by": self.flipped_by, "flip_kind": self.flip_kind,
            "risk": self.risk, "pace": self.pace, "label": self.label, "confidence": self.confidence,
            "reasons": self.reasons, "stage": self.stage, "ladder": self.ladder, "raider": self.raider,
            "ended": self.ended,
        }

    def public(self) -> dict:
        data = self.row()
        data["session"] = data.pop("session_id")
        return data


class SessionStore:
    def __init__(self) -> None:
        self.by_id: dict[str, Session] = {}
        self.by_fp: dict[str, str] = {}
        self.dirty: set[str] = set()

    def resolve(self, cookie: str | None, ip: str, user_agent: str) -> tuple[Session, bool]:
        """Return (session, is_new_cookie). Cookie first, fingerprint fallback."""
        fp = fingerprint(ip, user_agent)
        if cookie and cookie in self.by_id and not self.by_id[cookie].ended:
            session = self.by_id[cookie]
            self.by_fp[fp] = session.session_id
            return session, False
        if not cookie:
            known = self.by_fp.get(fp)
            if known and known in self.by_id and not self.by_id[known].ended:
                return self.by_id[known], True
        session_id = cookie if cookie and cookie.startswith("s_") and cookie not in self.by_id else new_session_id()
        session = Session(session_id=session_id, fingerprint=fp, src_ip=ip, user_agent=user_agent)
        self.by_id[session_id] = session
        self.by_fp[fp] = session_id
        self.dirty.add(session_id)
        return session, cookie != session_id

    def get(self, session_id: str) -> Session | None:
        return self.by_id.get(session_id)

    def touch(self, session: Session) -> None:
        self.dirty.add(session.session_id)

    def load(self, session: Session) -> None:
        self.by_id[session.session_id] = session
        self.by_fp[session.fingerprint] = session.session_id

    def active(self) -> list[Session]:
        return [s for s in self.by_id.values() if not s.ended]

    def end_all(self) -> list[Session]:
        ended = []
        for s in self.active():
            s.ended = True
            s.advance_stage("done")
            self.dirty.add(s.session_id)
            ended.append(s)
        self.by_fp.clear()
        return ended
