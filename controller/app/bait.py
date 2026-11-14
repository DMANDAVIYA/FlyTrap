"""Bait values in our own formats (never real provider formats)."""

from __future__ import annotations

import secrets
import string

B62 = string.digits + string.ascii_uppercase + string.ascii_lowercase
UPPER = string.ascii_uppercase + string.digits
WORDS = ["amber", "birch", "cedar", "delta", "ember", "fjord", "granite", "harbor", "indigo", "juniper", "kestrel", "lumen"]


def _pick(alphabet: str, n: int) -> str:
    return "".join(secrets.choice(alphabet) for _ in range(n))


def api_token() -> str:
    return "hl_live_" + _pick(B62, 24)


def cloud_key() -> tuple[str, str]:
    return "HLK" + _pick(UPPER, 17), "hlsk_" + _pick(B62, 32)


def canary_customer() -> str:
    return f"c{secrets.token_hex(4)}@{secrets.choice(WORDS)}-{secrets.choice(WORDS)}.example"


def demo_password(secret: str) -> str:
    """Password of the seeded real-side demo customer (same derivation as hlabs/app/bait.py)."""
    import hashlib
    import hmac
    raw = hmac.new(secret.encode(), b"demo-customer|password|0", hashlib.sha256).digest()
    number, digits = int.from_bytes(raw, "big"), []
    for _ in range(43):
        number, rest = divmod(number, 62)
        digits.append(B62[rest])
    return "".join(reversed(digits))[:16]
