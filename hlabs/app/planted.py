"""Values planted per visitor session through /_edge/plant (pods only).

`where` is normalised to one place:
    account       customer account page (default)
    api_keys      admin API keys page          ("api_keys", "admin/...", "api...")
    env           /.env                        ("env", ".env", "/.env")
    backup-01     backup-01 /.env.production   ("backup-01/...")
    model-vault   model-vault token file       ("model-vault/...")
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import ledger
from app.models import Planted

PREFIXES = (
    ("backup-01", "backup-01"),
    ("model-vault", "model-vault"),
    (".env", "env"),
    ("env", "env"),
    ("admin", "api_keys"),
    ("api", "api_keys"),
)


def normalize(where: str) -> str:
    cleaned = where.strip().lower().lstrip("/")
    for prefix, place in PREFIXES:
        if cleaned.startswith(prefix):
            return place
    return "account"


def add(db: Session, session_id: str, kind: str, value: str, where: str) -> Planted:
    row = Planted(session_id=session_id, kind=kind, value=value, place=normalize(where),
                  created_at=datetime.now(timezone.utc).replace(tzinfo=None))
    db.add(row)
    db.commit()
    return row


def rows(db: Session, session_id: str, place: str) -> list[Planted]:
    query = select(Planted).where(Planted.session_id == session_id, Planted.place == place).order_by(Planted.id)
    return list(db.scalars(query))


def show(db: Session, place: str) -> list[Planted]:
    """Planted rows for this visitor at a place, noted as shown bait."""
    ctx = ledger.current()
    found = rows(db, ctx.session_id, place)
    for row in found:
        ctx.add_bait(row.kind, row.value)
    return found


def header(found: list[Planted]) -> str:
    return ";".join(f"{row.kind}={row.value}" for row in found)
