"""Admin panel. Real side: staff accounts only. Pods also accept the
temporary migration login (ops-migrate) shown in the login page source."""

from datetime import date

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import console, exports, ledger, planted
from app.auth import ADMIN_COOKIE, admin_login, current_admin, log_in_admin
from app.db import get_db
from app.models import ApiToken, User
from app.web import page

router = APIRouter(prefix="/admin")
PAGE_SIZE = 50
RECENT_TOKENS = 25


class AdminLoginRequired(Exception):
    """Raised by require_admin; main.py turns it into a redirect to /admin/."""


def require_admin(request: Request, db: Session = Depends(get_db)) -> str:
    who = current_admin(request, db)
    if who is None:
        raise AdminLoginRequired()
    return who


@router.get("/")
def admin_home(request: Request, db: Session = Depends(get_db)) -> Response:
    if current_admin(request, db):
        return RedirectResponse("/admin/customers", status_code=303)
    return page(request, "admin/login.html", error=None)


@router.post("/login")
def admin_login_submit(request: Request, username: str = Form(""), password: str = Form(""),
                       db: Session = Depends(get_db)) -> Response:
    settings = request.app.state.settings
    identity = admin_login(settings, db, username.strip(), password)
    if identity is None:
        return page(request, "admin/login.html", status_code=401, error="Invalid username or password.")
    response = RedirectResponse("/admin/customers", status_code=303)
    log_in_admin(response, settings, identity)
    return response


@router.get("/logout")
def admin_logout() -> Response:
    response = RedirectResponse("/admin/", status_code=303)
    response.delete_cookie(ADMIN_COOKIE)
    return response


@router.get("/customers")
def customers(request: Request, page_no: int = Query(1, alias="page", ge=1), who: str = Depends(require_admin),
              db: Session = Depends(get_db)) -> Response:
    customer = User.role == "customer"
    total = db.scalar(select(func.count(User.id)).where(customer)) or 0
    pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    page_no = min(page_no, pages)
    rows = list(db.scalars(select(User).where(customer).order_by(User.id)
                           .offset((page_no - 1) * PAGE_SIZE).limit(PAGE_SIZE)))
    ledger.current().add_records("user", [row.id for row in rows])
    return page(request, "admin/customers.html", who=who, section="customers", rows=rows,
                total=total, page_no=page_no, pages=pages)


@router.get("/customers/export")
def customers_export(who: str = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    return exports.customers_csv(db, "page", f"customers_{date.today():%Y-%m-%d}.csv")


@router.get("/keys")
def keys(request: Request, who: str = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    service = [
        ("Platform deploy key", "api_token", ledger.show("api_token")),
        ("Object storage access key ID", "cloud_key_id", ledger.show("cloud_key_id")),
        ("Object storage secret", "cloud_secret", ledger.show("cloud_secret")),
    ]
    recent = list(db.execute(
        select(ApiToken, User.email).join(User, User.id == ApiToken.user_id)
        .order_by(ApiToken.created_at.desc()).limit(RECENT_TOKENS)
    ))
    ledger.current().add_records("token", [token.id for token, _ in recent])
    return page(request, "admin/keys.html", who=who, section="keys", service=service,
                extra=planted.show(db, "api_keys"), recent=recent)


@router.get("/infra")
def infra(request: Request, who: str = Depends(require_admin)) -> Response:
    return page(request, "admin/infra.html", who=who, section="infra", node=request.app.state.settings.node_name)


@router.get("/console")
def console_page(request: Request, who: str = Depends(require_admin)) -> Response:
    return page(request, "admin/console.html", who=who, section="console", command="", output="",
                node=request.app.state.settings.node_name)


@router.post("/console")
def console_run(request: Request, command: str = Form(""), who: str = Depends(require_admin)) -> Response:
    node = request.app.state.settings.node_name
    return page(request, "admin/console.html", who=who, section="console", command=command[:200],
                output=console.run(command[:200], node), node=node)
