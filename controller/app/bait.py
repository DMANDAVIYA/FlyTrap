"""Bait values in our own formats (never real provider formats).

Planted values are random and unique. The demo customer password is derived
with the same formula the site uses (hlabs/app/bait.py), so both sides agree
without sharing state.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import string

B62 = string.digits + string.ascii_uppercase + string.ascii_lowercase
UPPER = string.ascii_uppercase + string.digits
WORDS = ["amber", "birch", "cedar", "delta", "ember", "fjord", "granite", "harbor", "indigo", "juniper", "kestrel", "lumen"]
BASE62_DIGITS = 43  # 62**43 > 2**256


def _pick(alphabet: str, n: int) -> str:
    return "".join(secrets.choice(alphabet) for _ in range(n))


def api_token() -> str:
    return "hl_live_" + _pick(B62, 24)


def cloud_key() -> tuple[str, str]:
    return "HLK" + _pick(UPPER, 17), "hlsk_" + _pick(B62, 32)


def canary_customer() -> str:
    return f"c{secrets.token_hex(4)}@{secrets.choice(WORDS)}-{secrets.choice(WORDS)}.example"


def _base62(digest: bytes) -> str:
    number, digits = int.from_bytes(digest, "big"), []
    for _ in range(BASE62_DIGITS):
        number, rest = divmod(number, 62)
        digits.append(B62[rest])
    return "".join(reversed(digits))


def demo_password(secret: str) -> str:
    """Seeded demo customer's password; must match hlabs/app/bait.py demo_password."""
    digest = hmac.new(secret.encode(), b"demo-customer|password|0", hashlib.sha256).digest()
    return _base62(digest)[:16]
