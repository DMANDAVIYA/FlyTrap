"""What both islands share: who is asking, how fast to answer, what to report back.

Pods proxy every request here with:
    X-Edge-Session   visitor session id (derive bait values from it)
    X-Edge-Pace      normal | slow | drip | freeze, plus X-Edge-Drip-Rate
    X-Edge-Planted   kind=value;kind=value planted for this visitor on this island
Responses carry X-Edge-Bait / X-Edge-Records, which the pod passes on to the gateway.
"""

from dataclasses import dataclass, field
from html import escape

from fastapi import Request
from fastapi.responses import HTMLResponse

from app import bait

APACHE = "Apache/2.4.58 (Ubuntu)"


def parse_pairs(header: str) -> list[tuple[str, str]]:
    pairs = []
    for part in header.split(";"):
        kind, sep, value = part.strip().partition("=")
        if sep and kind and value:
            pairs.append((kind, value))
    return pairs


def drip_rate(header: str | None) -> float:
    try:
        return min(max(float(header or 2), 0.1), 1000.0)
    except ValueError:
        return 2.0


@dataclass
class Visitor:
    secret: str
    session_id: str
    pace: str
    rate: float
    planted: list[tuple[str, str]]
    shown: list[tuple[str, str]] = field(default_factory=list)

    @property
    def dripping(self) -> bool:
        return self.pace == "drip"

    def show(self, kind: str, place: str) -> str:
        value = bait.value(self.secret, self.session_id, kind, bait.PLACES[place])
        self.note(kind, value)
        return value

    def note(self, kind: str, value: str) -> None:
        if (kind, value) not in self.shown:
            self.shown.append((kind, value))

    def headers(self, records: str = "") -> dict[str, str]:
        out = {}
        if self.shown:
            out["X-Edge-Bait"] = ";".join(f"{kind}={value}" for kind, value in self.shown)
        if records:
            out["X-Edge-Records"] = records
        return out


def visitor(request: Request) -> Visitor:
    headers = request.headers
    return Visitor(
        secret=request.app.state.bait_secret,
        session_id=(headers.get("x-edge-session") or "s_anon")[:64],
        pace=headers.get("x-edge-pace", "normal"),
        rate=drip_rate(headers.get("x-edge-drip-rate")),
        planted=parse_pairs(headers.get("x-edge-planted", "")),
    )


def index_page(path: str, host: str, entries: list[tuple[str, str, str]]) -> HTMLResponse:
    """An Apache mod_autoindex listing. entries: (name, modified, size)."""
    rows = []
    if path != "/":
        rows.append('<tr><td valign="top">&nbsp;</td><td><a href="../">Parent Directory</a></td>'
                    '<td>&nbsp;</td><td align="right">  - </td><td>&nbsp;</td></tr>')
    for name, modified, size in entries:
        rows.append(f'<tr><td valign="top">&nbsp;</td><td><a href="{escape(name)}">{escape(name)}</a></td>'
                    f'<td align="right">{modified}  </td><td align="right">{size:>4}</td><td>&nbsp;</td></tr>')
    body = (
        '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">\n<html>\n <head>\n'
        f"  <title>Index of {path}</title>\n </head>\n <body>\n<h1>Index of {path}</h1>\n  <table>\n"
        '   <tr><th valign="top">&nbsp;</th><th><a href="?C=N;O=D">Name</a></th><th><a href="?C=M;O=A">'
        'Last modified</a></th><th><a href="?C=S;O=A">Size</a></th><th><a href="?C=D;O=A">Description</a></th></tr>\n'
        '   <tr><th colspan="5"><hr></th></tr>\n' + "\n".join(rows) + "\n"
        '   <tr><th colspan="5"><hr></th></tr>\n</table>\n'
        f"<address>{APACHE} Server at {host} Port 80</address>\n</body></html>\n"
    )
    return HTMLResponse(body)


def not_found_page(host: str, status: int = 404) -> HTMLResponse:
    title = "Not Found" if status == 404 else "Method Not Allowed"
    detail = ("The requested URL was not found on this server." if status == 404
              else "The requested method is not allowed for this URL.")
    body = (
        '<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">\n<html><head>\n'
        f"<title>{status} {title}</title>\n</head><body>\n<h1>{title}</h1>\n<p>{detail}</p>\n<hr>\n"
        f"<address>{APACHE} Server at {host} Port 80</address>\n</body></html>\n"
    )
    return HTMLResponse(body, status_code=status)
