"""Shared dependencies handed to tools, roles and raiders (one place to wire things)."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from .config import Settings
from .db import DB
from .gateway_client import GatewayClient


@dataclass
class SwarmState:
    """What the blue swarm remembers between turns. Reset by 'Reset Tartarus'."""

    demo_mode: bool = True
    planted: set[str] = field(default_factory=set)        # sessions Hephaestus already baited
    paced: set[tuple[str, str]] = field(default_factory=set)  # (mode, session) Cerberus already set
    blocked: set[str] = field(default_factory=set)
    reported: set[str] = field(default_factory=set)
    fingerprinted: set[str] = field(default_factory=set)
    suggested: set[str] = field(default_factory=set)
    rotated: set[str] = field(default_factory=set)
    damage_checked: set[str] = field(default_factory=set)
    linked_pairs: set[tuple[str, ...]] = field(default_factory=set)
    labels: dict[str, tuple[str, float]] = field(default_factory=dict)
    summaries: dict[str, dict] = field(default_factory=dict)
    lockdown_requested_at: float | None = None
    last_status: tuple | None = None                       # Athena's last status line, to avoid repeats

    def clear(self) -> None:
        """Forget everything except the demo-mode setting."""
        fresh = SwarmState(demo_mode=self.demo_mode)
        for name in self.__dataclass_fields__:
            setattr(self, name, getattr(fresh, name))


@dataclass
class Ctx:
    settings: Settings
    db: DB
    gw: GatewayClient
    http: httpx.AsyncClient
    state: SwarmState = field(default_factory=SwarmState)
