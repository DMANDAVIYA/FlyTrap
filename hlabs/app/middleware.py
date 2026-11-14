"""Reads the gateway's internal headers and reports bait and records back.

X-Edge-Block: 1        -> the site's own 403 page, any path
X-Edge-Pace: freeze    -> the site's own 503 maintenance page, any path
otherwise the response gets X-Edge-Bait / X-Edge-Records for what it showed.
"""

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import ledger
from app.web import error_page

DEFAULT_DRIP_RATE = 2.0


def drip_rate(header: str | None) -> float:
    try:
        rate = float(header) if header else DEFAULT_DRIP_RATE
    except ValueError:
        return DEFAULT_DRIP_RATE
    return min(max(rate, 0.1), 1000.0)


class EdgeContextMiddleware:
    def __init__(self, app: ASGIApp, bait_secret: str) -> None:
        self.app = app
        self.bait_secret = bait_secret

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        ctx = ledger.RequestContext(
            bait_secret=self.bait_secret,
            session_id=(headers.get("x-edge-session") or "s_anon")[:64],
            pod=headers.get("x-edge-pod", ""),
            pace=headers.get("x-edge-pace", "normal"),
            drip_rate=drip_rate(headers.get("x-edge-drip-rate")),
        )
        token = ledger.start(ctx)
        try:
            if headers.get("x-edge-block") == "1" or ctx.pace == "freeze":
                status = 403 if headers.get("x-edge-block") == "1" else 503
                await error_page(Request(scope), status)(scope, receive, send)
                return

            async def send_with_report(message: Message) -> None:
                if message["type"] == "http.response.start":
                    out = MutableHeaders(scope=message)
                    if ctx.bait:
                        out["X-Edge-Bait"] = ledger.bait_header(ctx)
                    if ctx.records:
                        out["X-Edge-Records"] = ledger.records_header(ctx)
                await send(message)

            await self.app(scope, receive, send_with_report)
        finally:
            ledger.finish(token)
