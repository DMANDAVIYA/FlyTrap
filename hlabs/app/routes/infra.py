"""Pods only: backup-01 and model-vault, reached through the admin panel and
the open /internal-backup/ directory. The customer CSV is built here from this
database so its rows match the admin panel."""

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app import exports, islands, ledger, planted
from app.db import get_db
from app.routes.admin import require_admin

router = APIRouter()
BACKUP_CSV = "customers_2026-11-01.csv"


def planted_header(request: Request, place: str) -> str:
    with request.app.state.db.session() as db:
        return planted.header(planted.rows(db, ledger.current().session_id, place))


@router.get(f"/admin/infra/backup-01/{BACKUP_CSV}")
def admin_backup_csv(who: str = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    return exports.customers_csv(db, "backup", BACKUP_CSV)


@router.get(f"/internal-backup/{BACKUP_CSV}")
def open_backup_csv(db: Session = Depends(get_db)) -> Response:
    return exports.customers_csv(db, "backup", BACKUP_CSV)


@router.get("/admin/infra/{island}/{path:path}")
async def admin_island(island: str, path: str, request: Request, who: str = Depends(require_admin)) -> Response:
    extra = await run_in_threadpool(planted_header, request, island)
    return await islands.forward(request, island, path, f"/admin/infra/{island}", extra)


@router.get("/internal-backup/{path:path}")
async def open_backup(path: str, request: Request) -> Response:
    extra = await run_in_threadpool(planted_header, request, "backup-01")
    return await islands.forward(request, "backup-01", path, "/internal-backup", extra)
