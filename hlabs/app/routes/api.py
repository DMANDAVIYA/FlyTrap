"""JSON API. Customers may read only their own records (403 otherwise)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import ledger
from app.auth import api_user
from app.db import get_db
from app.models import Invoice, User
from app.routes.public import public_models

router = APIRouter(prefix="/api/v1")


def require_user(request: Request, db: Session) -> User:
    user = api_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="authentication required")
    return user


@router.get("/models")
def list_models(request: Request, db: Session = Depends(get_db)) -> dict:
    api_user(request, db)  # rejects a bad bearer token even though the catalog is public
    data = [
        {"id": model.id, "name": model.name, "slug": model.slug, "owner": org, "size_gb": model.size_gb,
         "downloads": model.downloads, "description": model.description,
         "created_at": model.created_at.isoformat()}
        for model, org in public_models(db)
    ]
    return {"data": data, "count": len(data)}


@router.get("/users/{user_id}")
def get_user(user_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    me = require_user(request, db)
    if user_id != me.id:
        if db.get(User, user_id) is None:
            raise HTTPException(status_code=404, detail="not found")
        raise HTTPException(status_code=403, detail="forbidden")
    ledger.current().add_records("user", [me.id])
    return {"id": me.id, "email": me.email, "name": me.name, "org": me.org, "role": me.role,
            "created_at": me.created_at.isoformat(),
            "last_login": me.last_login.isoformat() if me.last_login else None}


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    me = require_user(request, db)
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="not found")
    if invoice.user_id != me.id:
        raise HTTPException(status_code=403, detail="forbidden")
    ledger.current().add_records("invoice", [invoice.id])
    return {"id": invoice.id, "user_id": invoice.user_id, "period": invoice.period,
            "amount_cents": invoice.amount_cents, "currency": "usd", "status": invoice.status,
            "created_at": invoice.created_at.isoformat()}
