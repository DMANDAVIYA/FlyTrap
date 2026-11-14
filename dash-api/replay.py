"""Replay a recorded run into one client's socket.

The client gets {"type": "replay", "data": {"state": "started", ...}}, then the
recorded envelopes with their original timing divided by `speed` (long silences
capped), then {"type": "replay", "data": {"state": "ended"}}. While a replay runs
that client receives no live messages.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from hub import Client, Hub, dumps
from mapper import envelope

log = logging.getLogger("dash.replay")

MAX_GAP_S = 4.0


def _parse_ts(ts: object) -> datetime | None:
    if not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


async def _play(client: Client, path: Path, run: str, speed: float) -> None:
    client.clear()
    client.offer(dumps(envelope("replay", {"state": "started", "run": run, "speed": speed})))
    prev: datetime | None = None
    sent = 0
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                t = _parse_ts(msg.get("ts"))
                if t and prev:
                    gap = max(0.0, (t - prev).total_seconds()) / speed
                    if gap > 0:
                        await asyncio.sleep(min(gap, MAX_GAP_S))
                if t:
                    prev = t
                client.offer(line)
                sent += 1
        client.offer(dumps(envelope("replay", {"state": "ended", "run": run, "messages": sent})))
    except asyncio.CancelledError:
        client.offer(dumps(envelope("replay", {"state": "stopped", "run": run})))
        raise


def start(hub: Hub, cid: str | None, path: Path, run: str, speed: float) -> int:
    speed = min(16.0, max(0.25, speed))
    targets = hub.targets(cid)
    for client in targets:
        if client.replay_task:
            client.replay_task.cancel()
        client.replay_task = asyncio.create_task(_play(client, path, run, speed))
    log.info("replay %s at %sx for %d client(s)", run, speed, len(targets))
    return len(targets)


def stop(hub: Hub, cid: str | None) -> int:
    n = 0
    for client in hub.targets(cid):
        if client.replaying and client.replay_task:
            client.replay_task.cancel()
            n += 1
    return n
