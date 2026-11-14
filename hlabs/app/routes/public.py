"""Marketing pages, the public model catalog, contact form, robots.txt, health."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import ledger
from app.db import get_db
from app.models import HostedModel, User
from app.web import page

router = APIRouter()

ROBOTS = """User-agent: *
Disallow: /account
Disallow: /admin/
Disallow: /internal-backup/
"""


@router.get("/")
def home(request: Request) -> Response:
    return page(request, "index.html")


@router.get("/pricing")
def pricing(request: Request) -> Response:
    return page(request, "pricing.html")


@router.get("/about")
def about(request: Request) -> Response:
    return page(request, "about.html")


def public_models(db: Session) -> list[tuple[HostedModel, str]]:
    query = (
        select(HostedModel, User.org)
        .join(User, User.id == HostedModel.owner_id)
        .where(HostedModel.visibility == "public")
        .order_by(HostedModel.downloads.desc())
    )
    rows = [(model, org) for model, org in db.execute(query)]
    ledger.current().add_records("model", [model.id for model, _ in rows])
    return rows


@router.get("/docs")
def docs(request: Request) -> Response:
    return page(request, "docs.html")


@router.get("/models")
def models(request: Request, db: Session = Depends(get_db)) -> Response:
    return page(request, "models.html", models=public_models(db))


@router.get("/contact")
def contact_form(request: Request) -> Response:
    return page(request, "contact.html", sent=False)


@router.post("/contact")
def contact_send(request: Request, name: str = Form(""), email: str = Form(""), message: str = Form(""),
                 company_website: str = Form("")) -> Response:
    return page(request, "contact.html", sent=True, name=name.strip())


@router.get("/robots.txt")
def robots() -> Response:
    return PlainTextResponse(ROBOTS)


@router.get("/healthz")
def healthz() -> dict:
    return {"ok": True}
