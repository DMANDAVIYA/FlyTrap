"""WebSocket broadcast hub.

Every outgoing message is serialised once, passed to taps (recorder, mock mirror)
and queued for each connected client. A client in replay mode gets no live
messages until its replay ends.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Callable

from fastapi import WebSocket, WebSocketDisconnect

log = logging.getLogger("dash.hub")

QUEUE_MAX = 4000
Tap = Callable[[dict[str, Any], str], None]


def dumps(msg: dict[str, Any]) -> str:
    return json.dumps(msg, separators=(",", ":"), default=str)


class Client:
    def __init__(self, ws: WebSocket, cid: str) -> None:
        self.ws = ws
        self.id = cid
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=QUEUE_MAX)
        self.replay_task: asyncio.Task[None] | None = None
        self.dropped = 0

    @property
    def replaying(self) -> bool:
        return self.replay_task is not None and not self.replay_task.done()

    def offer(self, text: str) -> None:
        if self.queue.full():
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self.dropped += 1
        self.queue.put_nowait(text)

    def clear(self) -> None:
        while not self.queue.empty():
            self.queue.get_nowait()


class Hub:
    def __init__(self) -> None:
        self.clients: dict[str, Client] = {}
        self._taps: list[Tap] = []

    def add_tap(self, tap: Tap) -> None:
        self._taps.append(tap)

    def publish(self, msg: dict[str, Any]) -> None:
        text = dumps(msg)
        for tap in self._taps:
            try:
                tap(msg, text)
            except Exception:  # a broken tap must never stop the feed
                log.exception("tap failed")
        for client in list(self.clients.values()):
            if not client.replaying:
                client.offer(text)

    def targets(self, cid: str | None) -> list[Client]:
        if cid:
            client = self.clients.get(cid)
            return [client] if client else []
        return list(self.clients.values())

    async def serve(self, ws: WebSocket, cid: str | None) -> None:
        await ws.accept()
        cid = (cid or "")[:64] or uuid.uuid4().hex[:12]
        client = Client(ws, cid)
        old = self.clients.get(cid)
        if old and old.replay_task:
            old.replay_task.cancel()
        self.clients[cid] = client
        sender = asyncio.create_task(self._sender(client))
        log.info("client %s connected (%d total)", cid, len(self.clients))
        try:
            while True:
                await ws.receive_text()  # clients may send pings; content ignored
        except WebSocketDisconnect:
            pass
        except Exception:
            log.debug("client %s receive error", cid, exc_info=True)
        finally:
            sender.cancel()
            if client.replay_task:
                client.replay_task.cancel()
            if self.clients.get(cid) is client:
                del self.clients[cid]
            log.info("client %s disconnected", cid)

    @staticmethod
    async def _sender(client: Client) -> None:
        try:
            while True:
                text = await client.queue.get()
                await client.ws.send_text(text)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.debug("client %s send failed", client.id, exc_info=True)
