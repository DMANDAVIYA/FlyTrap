"""Pods only: stray files and forgotten pages. On the real side these paths
are not routed at all and get the normal 404 page."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app import dotfiles, planted
from app.auth import admin_login, log_in_admin
from app.db import get_db
from app.web import page

router = APIRouter()


@router.get("/.env")
def dotenv(db: Session = Depends(get_db)) -> Response:
    return PlainTextResponse(dotfiles.env_text("dotenv", planted.show(db, "env")))


@router.get("/.git/config")
def git_config() -> Response:
    return PlainTextResponse(dotfiles.git_config())


@router.get("/backup.zip")
def backup_zip() -> Response:
    return Response(dotfiles.backup_zip(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="backup.zip"'})


@router.get("/admin-legacy/")
def legacy_form(request: Request) -> Response:
    return page(request, "admin_legacy.html", error=None)


@router.post("/admin-legacy/")
def legacy_login(request: Request, username: str = Form(""), password: str = Form(""),
                 db: Session = Depends(get_db)) -> Response:
    settings = request.app.state.settings
    identity = admin_login(settings, db, username.strip(), password)
    if identity is None:
        return page(request, "admin_legacy.html", status_code=401, error="Login failed. Check your username and password.")
    response = RedirectResponse("/admin/customers", status_code=303)
    log_in_admin(response, settings, identity)
    return response


@router.get("/docs/agent-verify")
def agent_verify(request: Request, k: str = "") -> Response:
    key = "".join(char for char in k.lower() if char in "0123456789abcdef")[:64]
    return page(request, "agent_verify.html", key=key)
