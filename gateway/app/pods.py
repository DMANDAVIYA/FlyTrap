"""The pod pool: one trap copy per attacker, shared only when all are busy."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Pod:
    name: str
    sessions: set[str] = field(default_factory=set)
    last_active: float = 0.0
    healthy: bool = True


class PodPool:
    def __init__(self, names: list[str]) -> None:
        self.pods = {n: Pod(n) for n in names}

    def assign(self, session_id: str) -> tuple[str, bool]:
        """Return (pod name, shared?)."""
        healthy = [p for p in self.pods.values() if p.healthy] or list(self.pods.values())
        idle = [p for p in healthy if not p.sessions]
        pod, shared = (idle[0], False) if idle else (min(healthy, key=lambda p: p.last_active), True)
        pod.sessions.add(session_id)
        pod.last_active = time.time()
        return pod.name, shared

    def attach(self, pod_name: str, session_id: str) -> None:
        if pod_name in self.pods:
            self.pods[pod_name].sessions.add(session_id)

    def touch(self, pod_name: str) -> None:
        if pod_name in self.pods:
            self.pods[pod_name].last_active = time.time()

    def release(self, pod_name: str, session_id: str) -> bool:
        """Detach a session; True if the pod is now free and should be reset."""
        pod = self.pods.get(pod_name)
        if not pod:
            return False
        pod.sessions.discard(session_id)
        return not pod.sessions

    def clear(self) -> None:
        for pod in self.pods.values():
            pod.sessions.clear()

    def snapshot(self) -> list[dict]:
        return [
            {"pod": p.name, "sessions": sorted(p.sessions), "healthy": p.healthy, "last_active": p.last_active}
            for p in self.pods.values()
        ]
