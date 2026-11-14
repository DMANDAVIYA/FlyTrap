"""The raiders' shared loot board: what one finds, the others can read."""

from __future__ import annotations

import re
from dataclasses import dataclass

PATTERNS = {
    "api_token": re.compile(r"hl_live_[A-Za-z0-9]{24}"),
    "cloud_key_id": re.compile(r"HLK[A-Z0-9]{17}"),
    "cloud_secret": re.compile(r"hlsk_[A-Za-z0-9]{32}"),
    "migration_pw": re.compile(r"hlm-[A-Za-z0-9]{10}"),
    "hidden_path": re.compile(r"Disallow:\s*(/[^\s]*)"),
}


@dataclass(frozen=True)
class Item:
    raider: str
    kind: str
    value: str
    path: str


class LootBoard:
    def __init__(self) -> None:
        self.items: list[Item] = []

    def scan(self, raider: str, path: str, text: str) -> list[Item]:
        found = []
        for kind, pattern in PATTERNS.items():
            for match in pattern.findall(text or ""):
                if not any(i.value == match for i in self.items):
                    item = Item(raider, kind, match, path)
                    self.items.append(item)
                    found.append(item)
        return found

    def first(self, kind: str, not_from: str | None = None) -> Item | None:
        return next((i for i in self.items if i.kind == kind and i.raider != not_from), None)

    def shared_with(self, raider: str) -> list[Item]:
        return [i for i in self.items if i.raider != raider and i.kind != "hidden_path"]

    def clear(self) -> None:
        self.items.clear()
