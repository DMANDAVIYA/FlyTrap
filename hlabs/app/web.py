"""Per-request context and rendering helpers.

Ctx carries the visitor id and pace sent by the front proxy, plus what this
response rendered (records and per-visitor values) for the X-Edge-* headers.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import Depends, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from . import models
from .bait import BaitLog
from .config import settings

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
AUTH_COOKIE, ADMIN_COOKIE = "hl_auth", "hl_admin"
AUTH_AGE = 7 * 24 * 3600
auth_signer = URLSafeTimedSerializer(settings.session_secret, salt="hl-auth")
admin_signer = URLSafeTimedSerializer(settings.session_secret, salt="hl-admin")


class Records:
    """Collects record ids and renders 'user:41,invoice:9001-9020'."""

    def __init__(self) -> None:
        self.ids: dict[str, set[int]] = {}

    def add(self, kind: str, *ids: int) -> None:
        self.ids.setdefault(kind, set()).update(int(i) for i in ids)

    def header(self) -> str:
        parts = []
        for kind, ids in self.ids.items():
            run: list[int] = []
            for i in sorted(ids) + [None]:  # type: ignore[list-item]
                if run and (i is None or i != run[-1] + 1):
                    parts.append(f"{kind}:{run[0]}" if len(run) == 1 else f"{kind}:{run[0]}-{run[-1]}")
                    run = []
                if i is not None:
                    run.append(i)
        return ",".join(parts)


@dataclass
class Ctx:
    request: Request
    db: Session
    sid: str
    pace: str
    drip_rate: int
    bait: BaitLog
    records: Records = field(default_factory=Records)
    _user: object = None
    _user_loaded: bool = False

    @property
    def user(self) -> models.User | None:
        if not self._user_loaded:
            self._user = current_user(self.request, self.db)
            self._user_loaded = True
        return self._user  # type: ignore[return-value]

    @property
    def admin(self) -> str | None:
        return current_admin(self.request, self.db)

    def headers(self) -> dict[str, str]:
        h = {}
        if self.records.ids:
            h["X-Edge-Records"] = self.records.header()
        if self.bait.items:
            h["X-Edge-Bait"] = self.bait.header()
        return h

    def finish(self, response: Response) -> Response:
        for k, v in self.headers().items():
            response.headers[k] = v
        return response


def get_db() -> Iterator[Session]:
    db = models.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_ctx(request: Request, db: Session = Depends(get_db)) -> Ctx:
    sid = request.headers.get("x-edge-session", "")[:64] or "anon"
    try:
        rate = int(request.headers.get("x-edge-drip-rate", "2"))
    except ValueError:
        rate = 2
    return Ctx(request, db, sid, request.headers.get("x-edge-pace", "normal"), max(1, min(rate, 100)), BaitLog(sid))


def render(ctx: Ctx, template: str, status: int = 200, **data) -> HTMLResponse:
    data.setdefault("user", ctx.user)
    data.setdefault("admin", None)
    data.setdefault("ai_note", "")
    resp = TEMPLATES.TemplateResponse(ctx.request, template, data, status_code=status)
    return ctx.finish(resp)  # type: ignore[return-value]


def current_user(request: Request, db: Session) -> models.User | None:
    raw = request.cookies.get(AUTH_COOKIE)
    if not raw:
        return None
    try:
        claims = auth_signer.loads(raw, max_age=AUTH_AGE)
    except BadSignature:
        return None
    if not isinstance(claims, dict) or not isinstance(claims.get("id"), int):
        return None
    user = db.get(models.User, claims["id"])
    if user is None and settings.is_pod:
        user = lazy_account(db, claims)
    if user is None:
        return None
    if not settings.is_pod and claims.get("v", 1) != user.session_version:
        return None
    return user


def lazy_account(db: Session, claims: dict) -> models.User | None:
    """A signed login for a user this copy doesn't know: create it with fresh history."""
    import random
    from datetime import date, timedelta

    from .seed import _token

    email, name = str(claims.get("email", ""))[:200], str(claims.get("name", ""))[:120]
    if not email or db.query(models.User).filter_by(email=email).first():
        return None
    rng = random.Random(claims["id"])
    user = models.User(id=claims["id"], email=email, name=name or email.split("@")[0], org=str(claims.get("org", ""))[:120],
                       plan="Team", role="customer", password_hash="")
    db.add(user)
    db.flush()
    db.add(models.ApiToken(user_id=user.id, token=_token(rng), label="ci-pipeline", scopes="models:read,inference"))
    next_id = (db.query(models.Invoice.id).order_by(models.Invoice.id.desc()).limit(1).scalar() or 1000) + 1
    for m in range(4):
        d = date(2026, 11, 1) - timedelta(days=30 * m)
        db.add(models.Invoice(id=next_id + m, user_id=user.id, period=d.strftime("%Y-%m"),
                              amount_cents=19900 + rng.randint(0, 5000), status="due" if m == 0 else "paid"))
    db.commit()
    return user


def login_cookie(user: models.User) -> str:
    return auth_signer.dumps({"id": user.id, "email": user.email, "name": user.name, "org": user.org,
                              "v": user.session_version})


def current_admin(request: Request, db: Session) -> str | None:
    raw = request.cookies.get(ADMIN_COOKIE)
    if not raw:
        return None
    try:
        data = admin_signer.loads(raw, max_age=AUTH_AGE)
    except BadSignature:
        return None
    name = data.get("u") if isinstance(data, dict) else None
    if name == "ops-migrate":
        return name if settings.is_pod else None
    admin = db.query(models.User).filter_by(email=name, role="admin").first() if name else None
    return admin.email if admin else None


def bearer(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("x-api-key", "").strip()
