"""Lockdown state machine: off -> countdown (10 s, cancellable) -> on -> off (Zeus only)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

COUNTDOWN_S = 10


class Lockdown:
    def __init__(self, on_change: Callable[[str, dict], None]) -> None:
        self.state = "off"
        self.reason = ""
        self._task: asyncio.Task | None = None
        self._notify = on_change

    @property
    def active(self) -> bool:
        return self.state == "on"

    def request(self, state: str, by: str, reason: str) -> tuple[bool, str]:
        if state == "countdown":
            if self.state != "off":
                return False, f"already {self.state}"
            self.state, self.reason = "countdown", reason
            self._task = asyncio.create_task(self._count(by))
            self._notify("countdown", {"seconds": COUNTDOWN_S, "reason": reason, "by": by})
            return True, "countdown started"
        if state == "on":
            if by != "zeus":
                return False, "only zeus can switch lockdown on directly"
            self._cancel_task()
            self.state, self.reason = "on", reason
            self._notify("on", {"reason": reason, "by": by})
            return True, "lockdown on"
        if state == "off":
            if by != "zeus":
                return False, "only zeus can end or cancel lockdown"
            self._cancel_task()
            previous, self.state = self.state, "off"
            self._notify("off", {"reason": reason or f"{previous} cancelled", "by": by})
            return True, "lockdown off"
        return False, "unknown state"

    async def _count(self, by: str) -> None:
        await asyncio.sleep(COUNTDOWN_S)
        if self.state == "countdown":
            self.state = "on"
            self._notify("on", {"reason": self.reason, "by": by})

    def _cancel_task(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None
