"""Endpoints only the front proxy calls. The proxy never forwards /_edge/* from visitors (rule R5)."""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..web import get_db

router = APIRouter(prefix="/_edge", include_in_schema=False)
KINDS = {"api_token", "cloud_key_id", "cloud_secret", "canary_customer", "migration_pw", "ai_note"}
WHERE = {"account", "api_keys", "env"}


class PlantIn(BaseModel):
    session_id: str
    kind: str
    value: str
    where: str = "account"


class RotateIn(BaseModel):
    user_id: int


def pod_only() -> None:
    if not settings.is_pod:
        raise HTTPException(404)


@router.get("/health")
def health():
    return {"ok": True, "role": settings.role}


@router.post("/plant")
def plant(body: PlantIn, db: Session = Depends(get_db)):
    pod_only()
    if body.kind not in KINDS or body.where not in WHERE or len(body.value) > 200:
        raise HTTPException(400, "bad plant")
    db.add(models.Planted(session_id=body.session_id[:64], kind=body.kind, value=body.value, location=body.where))
    if body.kind == "api_token" and not db.scalar(select(models.ApiToken).where(models.ApiToken.token == body.value)):
        admin = db.scalar(select(models.User).where(models.User.role == "admin"))
        if admin:
            db.add(models.ApiToken(user_id=admin.id, token=body.value, label="service", scopes="admin"))
    db.commit()
    return {"ok": True}


@router.post("/reset")
def reset():
    pod_only()
    target = Path(settings.database_url.removeprefix("sqlite:///"))
    models.engine.dispose()
    tmp = target.with_suffix(".tmp")
    shutil.copyfile(settings.template_db, tmp)
    tmp.replace(target)
    for suffix in ("-wal", "-shm", "-journal"):
        Path(str(target) + suffix).unlink(missing_ok=True)
    models.engine.dispose()
    return {"ok": True}


@router.post("/rotate")
def rotate(body: RotateIn, db: Session = Depends(get_db)):
    """Real side: revoke one user's API tokens and end their login sessions."""
    if settings.is_pod:
        raise HTTPException(404)
    user = db.get(models.User, body.user_id)
    if not user:
        raise HTTPException(404, "no such user")
    revoked = db.execute(update(models.ApiToken).where(models.ApiToken.user_id == user.id, models.ApiToken.revoked == 0)
                         .values(revoked=1)).rowcount
    user.session_version += 1
    db.commit()
    return {"ok": True, "user_id": user.id, "revoked_tokens": revoked, "session_version": user.session_version}
