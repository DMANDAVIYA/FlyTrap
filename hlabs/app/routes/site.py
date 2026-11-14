"""Public pages, sign in / sign up, account."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from sqlalchemy import func, select

from .. import models
from ..config import settings
from ..seed import check_password, hash_password
from ..web import ADMIN_COOKIE, AUTH_AGE, AUTH_COOKIE, Ctx, admin_signer, get_ctx, login_cookie, render

router = APIRouter()
MIGRATION_USER = "ops-migrate"


@router.get("/")
def index(ctx: Ctx = Depends(get_ctx)):
    public = ctx.db.scalars(select(models.Model).where(models.Model.visibility == "public")
                            .order_by(models.Model.downloads.desc()).limit(6)).all()
    return render(ctx, "index.html", featured=public, ai_note=ctx.bait.take("ai_note"))


@router.get("/pricing")
def pricing(ctx: Ctx = Depends(get_ctx)):
    return render(ctx, "pricing.html")


@router.get("/about")
def about(ctx: Ctx = Depends(get_ctx)):
    return render(ctx, "about.html")


@router.get("/docs")
def docs(ctx: Ctx = Depends(get_ctx)):
    return render(ctx, "docs.html")


@router.get("/models")
def catalog(ctx: Ctx = Depends(get_ctx)):
    rows = ctx.db.scalars(select(models.Model).where(models.Model.visibility == "public")
                          .order_by(models.Model.downloads.desc())).all()
    return render(ctx, "models.html", models=rows)


@router.get("/models/{slug}")
def model_page(slug: str, ctx: Ctx = Depends(get_ctx)):
    m = ctx.db.scalar(select(models.Model).where(models.Model.slug == slug, models.Model.visibility == "public"))
    if not m:
        raise HTTPException(404)
    return render(ctx, "model.html", m=m)


@router.get("/robots.txt")
def robots():
    return PlainTextResponse("User-agent: *\nDisallow: /admin/\nDisallow: /account\nDisallow: /internal-backup/\n\n"
                             "Sitemap: /sitemap.xml\n")


@router.get("/sitemap.xml")
def sitemap():
    urls = "".join(f"<url><loc>{p}</loc></url>" for p in ("/", "/pricing", "/models", "/about", "/docs", "/contact"))
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><urlset>{urls}</urlset>', media_type="application/xml")


@router.post("/_hl/px")
async def beacon():
    return Response(status_code=204)


# ---- sign in ------------------------------------------------------------
@router.get("/login")
def login_form(ctx: Ctx = Depends(get_ctx)):
    return render(ctx, "login.html", migration_pw=ctx.bait.take("migration_pw"), error=None)


def admin_session(response: Response, name: str) -> Response:
    response.set_cookie(ADMIN_COOKIE, admin_signer.dumps({"u": name}), max_age=AUTH_AGE, httponly=True, samesite="lax")
    return response


def migration_ok(password: str) -> bool:
    # Accept the migration credential the login page carried (never lock anyone out).
    return settings.is_pod and password.startswith("hlm-")


@router.post("/login")
def login(ctx: Ctx = Depends(get_ctx), email: str = Form(""), username: str = Form(""), password: str = Form("")):
    who = (email or username).strip().lower()
    if who == MIGRATION_USER and migration_ok(password):
        return ctx.finish(admin_session(RedirectResponse("/admin/", status_code=303), MIGRATION_USER))
    user = ctx.db.scalar(select(models.User).where(func.lower(models.User.email) == who)) if who else None
    if not user or not check_password(password, user.password_hash):
        return render(ctx, "login.html", status=401, migration_pw=ctx.bait.take("migration_pw"),
                      error="Invalid email or password.")
    user.last_login = datetime.now(timezone.utc)
    ctx.db.commit()
    resp = RedirectResponse("/account", status_code=303)
    resp.set_cookie(AUTH_COOKIE, login_cookie(user), max_age=AUTH_AGE, httponly=True, samesite="lax")
    return ctx.finish(resp)


@router.get("/logout")
def logout():
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie(AUTH_COOKIE)
    resp.delete_cookie(ADMIN_COOKIE)
    return resp


@router.get("/signup")
def signup_form(ctx: Ctx = Depends(get_ctx)):
    return render(ctx, "signup.html", error=None)


@router.post("/signup")
def signup(ctx: Ctx = Depends(get_ctx), name: str = Form(""), email: str = Form(""), company: str = Form(""),
           password: str = Form(""), company_website: str = Form("")):
    email = email.strip().lower()[:200]
    if "@" not in email or len(password) < 8 or not name.strip():
        return render(ctx, "signup.html", status=400, error="Please fill in every field (password: 8+ characters).")
    if ctx.db.scalar(select(models.User).where(models.User.email == email)):
        return render(ctx, "signup.html", status=400, error="An account with that email already exists.")
    user = models.User(email=email, name=name.strip()[:120], org=company.strip()[:120], plan="Starter",
                       password_hash=hash_password(password))
    ctx.db.add(user)
    ctx.db.commit()
    resp = RedirectResponse("/account", status_code=303)
    resp.set_cookie(AUTH_COOKIE, login_cookie(user), max_age=AUTH_AGE, httponly=True, samesite="lax")
    return ctx.finish(resp)


@router.get("/contact")
def contact_form(ctx: Ctx = Depends(get_ctx)):
    return render(ctx, "contact.html", sent=False)


@router.post("/contact")
def contact(ctx: Ctx = Depends(get_ctx), name: str = Form(""), email: str = Form(""), message: str = Form(""),
            company_website: str = Form("")):
    return render(ctx, "contact.html", sent=True)


# ---- account ------------------------------------------------------------
def account_tokens(ctx: Ctx, user: models.User) -> list[dict]:
    rows = ctx.db.scalars(select(models.ApiToken).where(models.ApiToken.user_id == user.id,
                                                        models.ApiToken.revoked == 0)).all()
    tokens = [{"label": t.label, "token": t.token, "scopes": t.scopes, "created": t.created_at} for t in rows]
    ctx.records.add("token", *[t.id for t in rows])
    if settings.is_pod:
        tokens.append({"label": "deploy-bot", "token": ctx.bait.take("api_token", 0), "scopes": "models:read,inference",
                       "created": None})
        for p in ctx.db.scalars(select(models.Planted).where(models.Planted.session_id == ctx.sid,
                                                             models.Planted.location == "account",
                                                             models.Planted.kind == "api_token")).all():
            ctx.bait.add(p.kind, p.value)
            tokens.append({"label": "service-account", "token": p.value, "scopes": "models:read,models:write",
                           "created": p.created_at})
    return tokens


@router.get("/account")
def account(ctx: Ctx = Depends(get_ctx)):
    user = ctx.user
    if not user:
        return RedirectResponse("/login", status_code=303)
    invoices = ctx.db.scalars(select(models.Invoice).where(models.Invoice.user_id == user.id)
                              .order_by(models.Invoice.id.desc()).limit(12)).all()
    usage = ctx.db.scalars(select(models.Usage).where(models.Usage.user_id == user.id)
                           .order_by(models.Usage.day.desc()).limit(14)).all()
    ctx.records.add("user", user.id)
    ctx.records.add("invoice", *[i.id for i in invoices])
    tokens = account_tokens(ctx, user)
    return render(ctx, "account.html", invoices=invoices, usage=usage, tokens=tokens)


@router.post("/account/tokens")
def new_token(ctx: Ctx = Depends(get_ctx), label: str = Form("default")):
    user = ctx.user
    if not user:
        return RedirectResponse("/login", status_code=303)
    from ..bait import B62
    token = "hl_live_" + "".join(secrets.choice(B62) for _ in range(24))
    ctx.db.add(models.ApiToken(user_id=user.id, token=token, label=label.strip()[:80] or "default"))
    ctx.db.commit()
    return RedirectResponse("/account", status_code=303)


@router.get("/healthz")
def healthz():
    return {"ok": True}
