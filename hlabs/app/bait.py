"""Per-visitor values, derived (never stored): HMAC(BAIT_SECRET, "sid|kind|n").

The same derivation lives in islands/app.py, so a value shown by the site and
a value shown by an internal host are consistent for one visitor.
Every value we render is reported back in the X-Edge-Bait response header.
"""

from __future__ import annotations

import hashlib
import hmac

from .config import settings

B62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
WORDS = ["amber", "birch", "cedar", "delta", "ember", "fjord", "granite", "harbor", "indigo", "juniper", "kestrel", "lumen"]


def _raw(session_id: str, kind: str, n: int) -> bytes:
    msg = f"{session_id}|{kind}|{n}".encode()
    return hmac.new(settings.bait_secret.encode(), msg, hashlib.sha256).digest()


def _encode(raw: bytes, alphabet: str, length: int) -> str:
    number = int.from_bytes(raw + hashlib.sha256(raw).digest(), "big")
    out = []
    for _ in range(length):
        number, rest = divmod(number, len(alphabet))
        out.append(alphabet[rest])
    return "".join(out)


def value(session_id: str, kind: str, n: int = 0) -> str:
    raw = _raw(session_id or "anon", kind, n)
    if kind == "api_token":
        return "hl_live_" + _encode(raw, B62, 24)
    if kind == "cloud_key_id":
        return "HLK" + _encode(raw, UPPER, 17)
    if kind == "cloud_secret":
        return "hlsk_" + _encode(raw, B62, 32)
    if kind == "migration_pw":
        return "hlm-" + _encode(raw, B62, 10)
    if kind == "ai_note":
        return raw.hex()[:16]
    if kind == "canary_customer":
        return f"c{raw.hex()[:8]}@{WORDS[raw[8] % len(WORDS)]}-{WORDS[raw[9] % len(WORDS)]}.example"
    raise ValueError(kind)


def demo_password(secret: str | None = None) -> str:
    """Password of the seeded real-side demo customer (matches the controller)."""
    key = (secret or settings.bait_secret).encode()
    raw = hmac.new(key, b"demo-customer|password|0", hashlib.sha256).digest()
    number, digits = int.from_bytes(raw, "big"), []
    for _ in range(43):
        number, rest = divmod(number, 62)
        digits.append(B62[rest])
    return "".join(reversed(digits))[:16]


class BaitLog:
    """Collects what a response rendered, for X-Edge-Bait."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.items: list[tuple[str, str]] = []

    def take(self, kind: str, n: int = 0) -> str:
        v = value(self.session_id, kind, n)
        if (kind, v) not in self.items:
            self.items.append((kind, v))
        return v

    def add(self, kind: str, v: str) -> None:
        if (kind, v) not in self.items:
            self.items.append((kind, v))

    def header(self) -> str:
        return ";".join(f"{k}={v}" for k, v in self.items)
