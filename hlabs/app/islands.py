"""Pods reach backup-01 and model-vault over trapnet and stream their answers back."""

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app import ledger

ISLANDS = ("backup-01", "model-vault")
ISLAND_PORT = 8000
PASSED_HEADERS = ("content-type", "content-disposition", "content-length", "last-modified")


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=3.0))


async def forward(request: Request, island: str, path: str, prefix: str, planted: str) -> StreamingResponse:
    if island not in ISLANDS:
        raise HTTPException(status_code=404)
    ctx = ledger.current()
    headers = {
        "X-Edge-Session": ctx.session_id,
        "X-Edge-Pace": ctx.pace,
        "X-Edge-Drip-Rate": str(ctx.drip_rate),
        "X-Forwarded-Prefix": prefix,
    }
    if ctx.pod:
        headers["X-Edge-Pod"] = ctx.pod
    if planted:
        headers["X-Edge-Planted"] = planted
    client: httpx.AsyncClient = request.app.state.http
    outgoing = client.build_request(
        "GET", f"http://{island}:{ISLAND_PORT}/{path}",
        params=list(request.query_params.multi_items()), headers=headers,
    )
    try:
        upstream = await client.send(outgoing, stream=True)
    except httpx.HTTPError as error:
        raise HTTPException(status_code=503) from error
    ledger.absorb(upstream.headers.get("x-edge-bait"), upstream.headers.get("x-edge-records"))
    passed = {name: upstream.headers[name] for name in PASSED_HEADERS if name in upstream.headers}
    location = upstream.headers.get("location", "")
    if location.startswith("/") and not location.startswith("//"):
        passed["location"] = location  # islands redirect under X-Forwarded-Prefix; never leak internal URLs
    return StreamingResponse(upstream.aiter_raw(), status_code=upstream.status_code, headers=passed,
                             background=BackgroundTask(upstream.aclose))
