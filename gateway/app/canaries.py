"""Canary registry: which visitor received which bait, and who used it."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Only stolen credentials and records count as canary use. The migration
# password is covered by tripwire T3, the AI note key by T7.
FIRING_KINDS = {"api_token", "cloud_key_id", "cloud_secret", "canary_customer"}
PATTERN = re.compile(
    r"hl_live_[A-Za-z0-9]{24}|HLK[A-Z0-9]{17}|hlsk_[A-Za-z0-9]{32}|c[0-9a-f]{8}@[a-z]+-[a-z]+\.example"
)


@dataclass
class Canary:
    value: str
    kind: str
    session_id: str
    location: str = ""


@dataclass
class Firing:
    canary: Canary
    used_by: str


def parse_bait_header(header: str) -> list[tuple[str, str]]:
    """'kind=value;kind=value' -> [(kind, value), ...]"""
    pairs = []
    for part in header.split(";"):
        kind, sep, value = part.strip().partition("=")
        if sep and kind and value:
            pairs.append((kind.strip(), value.strip()))
    return pairs


def parse_records_header(header: str) -> list[str]:
    """'user:41,invoice:9001-9020' -> ['user:41', 'invoice:9001-9020'] (ranges kept compact)."""
    return [p.strip() for p in header.split(",") if ":" in p][:500]


def count_records(records: list[str]) -> int:
    total = 0
    for rec in records:
        _, _, ident = rec.partition(":")
        first, sep, last = ident.partition("-")
        if sep and first.isdigit() and last.isdigit():
            total += max(0, int(last) - int(first) + 1)
        else:
            total += 1
    return total


class CanaryRegistry:
    def __init__(self) -> None:
        self.by_value: dict[str, Canary] = {}
        self.pending: list[Canary] = []

    def register(self, canary: Canary) -> bool:
        if canary.value in self.by_value:
            return False
        self.by_value[canary.value] = canary
        self.pending.append(canary)
        return True

    def scan(self, text: str, session_id: str) -> list[Firing]:
        firings, seen = [], set()
        for value in PATTERN.findall(text):
            canary = self.by_value.get(value)
            if canary and canary.kind in FIRING_KINDS and value not in seen:
                seen.add(value)
                firings.append(Firing(canary, session_id))
        return firings

    def drain(self) -> list[Canary]:
        out, self.pending = self.pending, []
        return out
