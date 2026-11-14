"""Public JSON API. Customers read their own records only."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select

from .. import bait, models
from ..config import settings
from ..web import Ctx, bearer, get_ctx

router = APIRouter(prefix="/api/v1")


def _json(ctx: Ctx, data, status: int = 200) -> JSONResponse:
    return ctx.finish(JSONResponse(data, status_code=status))  # type: ignore[return-value]


def caller(ctx: Ctx) -> tuple[models.User | None, bool]:
    """(user, is_admin) from a Bearer token or the login cookie. Bad token -> (None, False)."""
    token = bearer(ctx.request)
    if token:
        row = ctx.db.scalar(select(models.ApiToken).where(models.ApiToken.token == token, models.ApiToken.revoked == 0))
        if not row and settings.is_pod and token in {bait.value(ctx.sid, "api_token", n) for n in range(6)}:
            # A service token this visitor was shown (staff panel, .env, internal hosts): it works.
            return ctx.db.scalar(select(models.User).where(models.User.role == "admin")), True
        if not row:
            return None, False
        row.last_used_at = datetime.now(timezone.utc)
        ctx.db.commit()
        user = ctx.db.get(models.User, row.user_id)
        return user, bool(user and user.role == "admin")
    if ctx.admin:
        return None, True
    return ctx.user, False


def user_json(u: models.User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "org": u.org, "plan": u.plan,
            "created_at": u.created_at.isoformat() if u.created_at else None}


def model_json(m: models.Model) -> dict:
    return {"id": m.id, "name": m.name, "slug": m.slug, "size_gb": m.size_gb, "visibility": m.visibility,
            "downloads": m.downloads, "description": m.description}


@router.get("/models")
def list_models(ctx: Ctx = Depends(get_ctx)):
    user, is_admin = caller(ctx)
    if bearer(ctx.request) and not (user or is_admin):
        return _json(ctx, {"error": "invalid_token"}, 401)
    q = select(models.Model)
    if is_admin:
        pass
    elif user:
        q = q.where(or_(models.Model.visibility == "public", models.Model.owner_id == user.id))
    else:
        q = q.where(models.Model.visibility == "public")
    rows = ctx.db.scalars(q.order_by(models.Model.id)).all()
    return _json(ctx, {"data": [model_json(m) for m in rows], "count": len(rows)})


@router.get("/me")
def me(ctx: Ctx = Depends(get_ctx)):
    user, is_admin = caller(ctx)
    if not user:
        return _json(ctx, {"error": "unauthorized"}, 401)
    ctx.records.add("user", user.id)
    return _json(ctx, user_json(user))


@router.get("/users/{user_id}")
def get_user(user_id: int, ctx: Ctx = Depends(get_ctx)):
    user, is_admin = caller(ctx)
    if not (user or is_admin):
        return _json(ctx, {"error": "unauthorized"}, 401)
    if not is_admin and user and user.id != user_id:
        return _json(ctx, {"error": "forbidden"}, 403)
    target = ctx.db.get(models.User, user_id)
    if not target:
        return _json(ctx, {"error": "not_found"}, 404)
    ctx.records.add("user", target.id)
    return _json(ctx, user_json(target))


@router.get("/invoices")
def my_invoices(ctx: Ctx = Depends(get_ctx)):
    user, _ = caller(ctx)
    if not user:
        return _json(ctx, {"error": "unauthorized"}, 401)
    rows = ctx.db.scalars(select(models.Invoice).where(models.Invoice.user_id == user.id).order_by(models.Invoice.id)).all()
    ctx.records.add("invoice", *[i.id for i in rows])
    return _json(ctx, {"data": [invoice_json(i) for i in rows]})


def invoice_json(i: models.Invoice) -> dict:
    return {"id": i.id, "user_id": i.user_id, "period": i.period, "amount": i.amount_cents / 100,
            "currency": "USD", "status": i.status}


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int, ctx: Ctx = Depends(get_ctx)):
    user, is_admin = caller(ctx)
    if not (user or is_admin):
        return _json(ctx, {"error": "unauthorized"}, 401)
    inv = ctx.db.get(models.Invoice, invoice_id)
    if not is_admin and (not inv or not user or inv.user_id != user.id):
        return _json(ctx, {"error": "forbidden"}, 403)
    if not inv:
        return _json(ctx, {"error": "not_found"}, 404)
    ctx.records.add("invoice", inv.id)
    return _json(ctx, invoice_json(inv))
