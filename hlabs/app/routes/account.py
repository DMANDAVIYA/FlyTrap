"""Customer login, signup and the account page."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import ledger, planted
from app.auth import (
    AUTH_COOKIE,
    MIGRATION_USER,
    admin_login,
    current_user,
    hash_password,
    log_in,
    log_in_admin,
    new_api_token,
    password_ok,
)
from app.db import get_db
from app.models import ApiToken, Invoice, Usage, User
from app.web import page

router = APIRouter()

CHART_WIDTH, CHART_HEIGHT = 720, 180


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def safe_next(target: str) -> str:
    local = target.startswith("/") and not target.startswith("//") and "\\" not in target
    return target if local else "/account"


@router.get("/login")
def login_form(request: Request, next: str = "/account") -> Response:
    return page(request, "login.html", next=safe_next(next), error=None, email="")


@router.post("/login")
def login(request: Request, email: str = Form(""), password: str = Form(""), next: str = Form("/account"),
          db: Session = Depends(get_db)) -> Response:
    settings = request.app.state.settings
    email = email.strip().lower()
    if settings.is_pod and email == MIGRATION_USER and admin_login(settings, db, email, password):
        response = RedirectResponse("/admin/customers", status_code=303)
        log_in_admin(response, settings, MIGRATION_USER)
        return response
    user = db.scalar(select(User).where(User.email == email))
    if not user or not password_ok(settings, user, password):
        return page(request, "login.html", status_code=401, next=safe_next(next),
                    error="Incorrect email or password.", email=email)
    user.last_login = utcnow()
    db.commit()
    response = RedirectResponse(safe_next(next), status_code=303)
    log_in(response, settings, user)
    return response


@router.get("/logout")
def logout() -> Response:
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(AUTH_COOKIE)
    return response


@router.get("/signup")
def signup_form(request: Request) -> Response:
    return page(request, "signup.html", error=None, form={})


def signup_error(db: Session, name: str, email: str, password: str) -> str | None:
    if not name or "@" not in email or "." not in email.partition("@")[2]:
        return "Please enter your name and a valid work email."
    if len(password) < 8:
        return "Passwords need at least 8 characters."
    if db.scalar(select(User.id).where(User.email == email)):
        return "An account with this email already exists."
    return None


@router.post("/signup")
def signup(request: Request, name: str = Form(""), email: str = Form(""), org: str = Form(""),
           password: str = Form(""), company_website: str = Form(""), db: Session = Depends(get_db)) -> Response:
    name, email, org = name.strip(), email.strip().lower(), org.strip()
    error = signup_error(db, name, email, password)
    if error:
        return page(request, "signup.html", status_code=400, error=error,
                    form={"name": name, "email": email, "org": org})
    now = utcnow()
    user = User(email=email, name=name, org=org or "Personal", role="customer",
                password_hash=hash_password(password), created_at=now, last_login=now, session_version=0)
    db.add(user)
    db.flush()
    db.add(ApiToken(user_id=user.id, token=new_api_token(), label="Default key",
                    scopes="inference models:read", created_at=now))
    db.commit()
    response = RedirectResponse("/account", status_code=303)
    log_in(response, request.app.state.settings, user)
    return response


def usage_chart(rows: list[Usage]) -> dict:
    """Bar geometry for the inline SVG usage chart."""
    peak = max((row.requests for row in rows), default=0) or 1
    slot = CHART_WIDTH / max(len(rows), 1)
    bars = []
    for index, row in enumerate(rows):
        height = round(row.requests / peak * (CHART_HEIGHT - 24), 1)
        bars.append({"x": round(index * slot + 2, 1), "y": round(CHART_HEIGHT - height, 1),
                     "w": round(slot - 4, 1), "h": height, "label": f"{row.day:%b %d}: {row.requests:,} requests"})
    return {"width": CHART_WIDTH, "height": CHART_HEIGHT, "bars": bars, "peak": peak,
            "requests": sum(row.requests for row in rows), "tokens": sum(row.tokens for row in rows)}


@router.get("/account")
def account(request: Request, db: Session = Depends(get_db)) -> Response:
    user = current_user(request, db)
    if user is None:
        return RedirectResponse("/login?next=/account", status_code=303)
    tokens = list(db.scalars(select(ApiToken).where(ApiToken.user_id == user.id).order_by(ApiToken.created_at.desc())))
    invoices = list(db.scalars(select(Invoice).where(Invoice.user_id == user.id).order_by(Invoice.period.desc())))
    usage = list(db.scalars(select(Usage).where(Usage.user_id == user.id).order_by(Usage.day.desc()).limit(30)))
    ctx = ledger.current()
    ctx.add_records("user", [user.id])
    ctx.add_records("token", [token.id for token in tokens])
    ctx.add_records("invoice", [invoice.id for invoice in invoices])
    return page(request, "account.html", user=user, tokens=tokens, extra_keys=planted.show(db, "account"),
                invoices=invoices, chart=usage_chart(usage[::-1]))
