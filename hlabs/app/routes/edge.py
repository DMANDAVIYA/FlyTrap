"""Internal endpoints the gateway calls (spec 6.5). The gateway never lets the
public reach /_edge/* (rule R5)."""

import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.orm import Session

from app import planted
from app.db import get_db
from app.models import ApiToken, User

pod_router = APIRouter(prefix="/_edge")
real_router = APIRouter(prefix="/_edge")


class PlantIn(BaseModel):
    session_id: str
    kind: str
    value: str
    where: str = "account"


class RotateIn(BaseModel):
    user_id: int
    reason: str = ""


def health(request: Request) -> dict:
    settings = request.app.state.settings
    return {"ok": True, "role": settings.role, "name": settings.pod_name or settings.node_name}


pod_router.add_api_route("/health", health, methods=["GET"])
real_router.add_api_route("/health", health, methods=["GET"])


@pod_router.post("/plant")
def plant(body: PlantIn, db: Session = Depends(get_db)) -> dict:
    row = planted.add(db, body.session_id, body.kind, body.value, body.where)
    return {"ok": True, "id": row.id, "place": row.place}


@pod_router.post("/reset")
def reset(request: Request) -> dict:
    started = time.perf_counter()
    request.app.state.db.restore(Path(request.app.state.settings.template_db))
    return {"ok": True, "ms": round((time.perf_counter() - started) * 1000, 1)}


@real_router.post("/rotate")
def rotate(body: RotateIn, db: Session = Depends(get_db)) -> JSONResponse:
    user = db.get(User, body.user_id)
    if user is None:
        return JSONResponse({"ok": False, "error": f"unknown user {body.user_id}"}, status_code=404)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    revoked = db.execute(
        update(ApiToken).where(ApiToken.user_id == user.id, ApiToken.revoked_at.is_(None)).values(revoked_at=now)
    ).rowcount
    user.session_version += 1
    db.commit()
    return JSONResponse({"ok": True, "user_id": user.id, "revoked": revoked, "session_version": user.session_version})
