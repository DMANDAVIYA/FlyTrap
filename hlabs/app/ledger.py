"""Per-request context: who the visitor is (X-Edge-Session) and what bait and
records this response showed, reported back to the gateway as
X-Edge-Bait and X-Edge-Records (spec 10.4, 10.5).
"""

from collections.abc import Iterable
from contextvars import ContextVar
from dataclasses import dataclass, field

from app import bait


@dataclass
class RequestContext:
    bait_secret: str = ""
    session_id: str = "s_anon"
    pod: str = ""
    pace: str = "normal"
    drip_rate: float = 2.0
    bait: list[tuple[str, str]] = field(default_factory=list)
    records: dict[str, set[int]] = field(default_factory=dict)

    def add_bait(self, kind: str, value: str) -> None:
        if (kind, value) not in self.bait:
            self.bait.append((kind, value))

    def add_records(self, kind: str, ids: Iterable[int]) -> None:
        self.records.setdefault(kind, set()).update(ids)

    @property
    def dripping(self) -> bool:
        return self.pace == "drip"


_current: ContextVar[RequestContext | None] = ContextVar("hl_request", default=None)


def start(ctx: RequestContext) -> object:
    return _current.set(ctx)


def finish(token: object) -> None:
    _current.reset(token)  # type: ignore[arg-type]


def current() -> RequestContext:
    return _current.get() or RequestContext()


def show(kind: str, place: str = "page") -> str:
    """Derive this visitor's bait value for a place and note it as shown."""
    ctx = current()
    value = bait.value(ctx.bait_secret, ctx.session_id, kind, bait.PLACES[place])
    ctx.add_bait(kind, value)
    return value


def absorb(bait_header: str | None, records_header: str | None) -> None:
    """Merge X-Edge-Bait / X-Edge-Records reported by an upstream island."""
    ctx = current()
    for kind, value in parse_bait(bait_header or ""):
        ctx.add_bait(kind, value)
    for kind, ids in parse_records(records_header or ""):
        ctx.add_records(kind, ids)


def bait_header(ctx: RequestContext) -> str:
    return ";".join(f"{kind}={value}" for kind, value in ctx.bait)


def records_header(ctx: RequestContext) -> str:
    parts = []
    for kind in sorted(ctx.records):
        for first, last in runs(sorted(ctx.records[kind])):
            parts.append(f"{kind}:{first}" if first == last else f"{kind}:{first}-{last}")
    return ",".join(parts)


def runs(ids: list[int]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for item in ids:
        if result and item == result[-1][1] + 1:
            result[-1] = (result[-1][0], item)
        else:
            result.append((item, item))
    return result


def parse_bait(header: str) -> list[tuple[str, str]]:
    pairs = []
    for part in header.split(";"):
        kind, sep, value = part.strip().partition("=")
        if sep and kind and value:
            pairs.append((kind, value))
    return pairs


def parse_records(header: str) -> list[tuple[str, range]]:
    result = []
    for part in header.split(","):
        kind, sep, span = part.strip().partition(":")
        first, _, last = span.partition("-")
        if sep and first.isdigit() and (not last or last.isdigit()):
            result.append((kind, range(int(first), int(last or first) + 1)))
    return result
