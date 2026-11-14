"""Low-level forwarding: header hygiene and streaming. No policy lives here."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

HOP_BY_HOP = {
    "connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade",
    "proxy-authorization", "proxy-authenticate", "host", "content-length",
}
DROP_FROM_UPSTREAM = HOP_BY_HOP - {"content-length"} | {"server", "date"}
INTERNAL_PREFIXES = ("x-edge-", "x-raider")


def is_internal(name: str) -> bool:
    return name.lower().startswith(INTERNAL_PREFIXES)


def request_headers(raw: list[tuple[str, str]], public_host: str, extra: dict[str, str]) -> list[tuple[str, str]]:
    """Visitor headers minus hop-by-hop and any spoofed internal headers, plus our own."""
    headers = [(k, v) for k, v in raw if k.lower() not in HOP_BY_HOP and not is_internal(k)]
    headers.append(("host", public_host))
    headers.extend(extra.items())
    return headers


def response_headers(upstream: httpx.Headers, public_base: str, upstream_base: str) -> tuple[list[tuple[str, str]], dict[str, str]]:
    """Split upstream headers into (what the visitor sees, internal headers we consume)."""
    visible, internal = [], {}
    for k, v in upstream.multi_items():
        lk = k.lower()
        if is_internal(lk):
            internal[lk] = v
        elif lk not in DROP_FROM_UPSTREAM:
            if lk == "location" and v.startswith(upstream_base):
                v = public_base + v[len(upstream_base):]
            visible.append((k, v))
    return visible, internal


async def open_upstream(client: httpx.AsyncClient, method: str, url: str, headers: list[tuple[str, str]],
                        body: bytes | AsyncIterator[bytes]) -> httpx.Response:
    req = client.build_request(method, url, headers=headers, content=body)
    return await client.send(req, stream=True)
