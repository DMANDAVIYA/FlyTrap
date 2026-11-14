"""Shared dependencies handed to tools, roles and raiders (one place to wire things)."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from .config import Settings
from .db import DB
from .gateway_client import GatewayClient


@dataclass
class SwarmState:
    demo_mode: bool = True
    released: bool = False
    planted: set[str] = field(default_factory=set)        # sessions Hephaestus already baited
    paced: set[str] = field(default_factory=set)
    reported: set[str] = field(default_factory=set)
    fingerprinted: set[str] = field(default_factory=set)
    suggested: set[str] = field(default_factory=set)
    rotated: set[str] = field(default_factory=set)
    damage_checked: set[str] = field(default_factory=set)
    linked_pairs: set[tuple[str, ...]] = field(default_factory=set)
    labels: dict[str, tuple[str, float]] = field(default_factory=dict)
    summaries: dict[str, dict] = field(default_factory=dict)

    def clear(self) -> None:
        demo = self.demo_mode
        self.__init__()
        self.demo_mode = demo


@dataclass
class Ctx:
    settings: Settings
    db: DB
    gw: GatewayClient
    http: httpx.AsyncClient
    state: SwarmState = field(default_factory=SwarmState)
