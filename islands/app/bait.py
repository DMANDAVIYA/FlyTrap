"""Per-session bait values (spec 10.4). Pure functions, no app imports.

islands/app/bait.py is a byte-identical copy (checked by hlabs/tests/test_bait.py).

    raw = HMAC_SHA256(BAIT_SECRET, f"{session_id}|{kind}|{n}")

base62: the digest read as a big-endian integer, written with the alphabet
0-9A-Za-z, left-padded to 43 digits; a kind takes the first N digits.
cloud_key_id upper-cases those digits. Hex kinds use raw.hex().

The demo customer password (spec 10.3) is the first 16 base62 digits of
raw(secret, "demo-customer", "password", 0).
"""

import hashlib
import hmac

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
DIGITS = 43  # 62**43 > 2**256

KINDS = ("api_token", "cloud_key_id", "cloud_secret", "migration_pw", "ai_note", "canary_customer")

# Each place a value is shown in uses its own n, so every copy is distinct
# and a leaked value tells us where it was taken from.
PLACES = {"page": 0, "dotenv": 1, "git": 2, "zip": 3, "backup": 4, "vault": 5}

DOMAIN_WORDS = (
    "amber", "birch", "cedar", "delta", "ember", "fjord", "granite", "harbor",
    "indigo", "juniper", "kelp", "lumen", "maple", "north", "onyx", "prairie",
    "quartz", "river", "summit", "tidal", "upland", "valley", "willow", "zephyr",
)


def raw(secret: str, session_id: str, kind: str, n: int = 0) -> bytes:
    message = f"{session_id}|{kind}|{n}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).digest()


def base62(digest: bytes) -> str:
    number = int.from_bytes(digest, "big")
    digits = []
    for _ in range(DIGITS):
        number, rest = divmod(number, 62)
        digits.append(ALPHABET[rest])
    return "".join(reversed(digits))


def value(secret: str, session_id: str, kind: str, n: int = 0) -> str:
    digest = raw(secret, session_id, kind, n)
    text = base62(digest)
    if kind == "api_token":
        return "hl_live_" + text[:24]
    if kind == "cloud_key_id":
        return "HLK" + text[:17].upper()
    if kind == "cloud_secret":
        return "hlsk_" + text[:32]
    if kind == "migration_pw":
        return "hlm-" + text[:10]
    if kind == "ai_note":
        return digest.hex()[:16]
    if kind == "canary_customer":
        first = DOMAIN_WORDS[digest[8] % len(DOMAIN_WORDS)]
        second = DOMAIN_WORDS[digest[9] % len(DOMAIN_WORDS)]
        return f"c{digest.hex()[:8]}@{first}-{second}.example"
    raise ValueError(f"unknown bait kind: {kind}")


def demo_password(secret: str) -> str:
    return base62(raw(secret, "demo-customer", "password", 0))[:16]
