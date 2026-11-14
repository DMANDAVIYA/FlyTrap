"""Shared helpers for the two internal hosts.

Per-visitor values use the same derivation as hlabs/app/bait.py, keyed by the
X-Edge-Session header the web app passes through. Every response lists what it
served in X-Edge-Records / X-Edge-Bait, and downloads honour X-Edge-Pace.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os

from fastapi import Request

SECRET = os.getenv("BAIT_SECRET", "dev-bait-secret").encode()
B62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
WORDS = ["amber", "birch", "cedar", "delta", "ember", "fjord", "granite", "harbor", "indigo", "juniper", "kestrel", "lumen"]


def _encode(raw: bytes, alphabet: str, length: int) -> str:
    number = int.from_bytes(raw + hashlib.sha256(raw).digest(), "big")
    out = []
    for _ in range(length):
        number, rest = divmod(number, len(alphabet))
        out.append(alphabet[rest])
    return "".join(out)


def value(session_id: str, kind: str, n: int = 0) -> str:
    raw = hmac.new(SECRET, f"{session_id or 'anon'}|{kind}|{n}".encode(), hashlib.sha256).digest()
    if kind == "api_token":
        return "hl_live_" + _encode(raw, B62, 24)
    if kind == "cloud_key_id":
        return "HLK" + _encode(raw, UPPER, 17)
    if kind == "cloud_secret":
        return "hlsk_" + _encode(raw, B62, 32)
    if kind == "canary_customer":
        return f"c{raw.hex()[:8]}@{WORDS[raw[8] % len(WORDS)]}-{WORDS[raw[9] % len(WORDS)]}.example"
    raise ValueError(kind)


class Visit:
    def __init__(self, request: Request) -> None:
        self.sid = request.headers.get("x-edge-session", "")[:64] or "anon"
        self.pace = request.headers.get("x-edge-pace", "normal")
        try:
            self.rate = max(1, min(int(request.headers.get("x-edge-drip-rate", "2")), 100))
        except ValueError:
            self.rate = 2
        self.bait: list[tuple[str, str]] = []
        self.records: list[str] = []

    def take(self, kind: str, n: int = 0) -> str:
        v = value(self.sid, kind, n)
        self.bait.append((kind, v))
        return v

    def headers(self, **extra: str) -> dict[str, str]:
        h = dict(extra)
        if self.bait:
            h["X-Edge-Bait"] = ";".join(f"{k}={v}" for k, v in self.bait)
        if self.records:
            h["X-Edge-Records"] = ",".join(self.records)
        return h

    @property
    def drip(self) -> bool:
        return self.pace == "drip"


async def drip_lines(lines: list[bytes], rate: int):
    for line in lines:
        yield line
        await asyncio.sleep(1 / rate)


async def drip_bytes(data_iter, rate: int):
    """Rate is rows/s for text; for binary we send one 64 KB chunk per tick."""
    for chunk in data_iter:
        yield chunk
        await asyncio.sleep(1 / rate)


def listing(title: str, entries: list[tuple[str, str, str]]) -> str:
    """nginx-style autoindex. entries: (name, modified, size). Links are relative."""
    rows = "\n".join(f'<a href="{n}">{n}</a>{" " * max(1, 51 - len(n))}{m}  {s:>10}' for n, m, s in entries)
    return (f"<html>\n<head><title>Index of {title}</title></head>\n<body>\n<h1>Index of {title}</h1><hr><pre>"
            f'<a href="../">../</a>\n{rows}\n</pre><hr></body>\n</html>\n')
