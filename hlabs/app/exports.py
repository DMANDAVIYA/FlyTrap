"""Customer CSV export: the admin panel's button and backup-01's nightly file.

Rows come from this database plus the visitor's own unique customer row.
With X-Edge-Pace: drip the rows trickle out at X-Edge-Drip-Rate per second.
"""

import asyncio
import csv
import io
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import bait, ledger
from app.models import User
from app.seed import org_from_email

COLUMNS = ["id", "name", "email", "org", "created_at", "last_login"]
FIRST_NAMES = ("Avery", "Jordan", "Riley", "Morgan", "Casey", "Quinn", "Rowan", "Elliot", "Harper", "Sasha")
LAST_NAMES = ("Lindqvist", "Marlowe", "Okonkwo", "Delacroix", "Brennan", "Castillo", "Haddad", "Novak", "Ashby", "Ferreira")


def iso(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else ""


def visitor_row(place: str, row_id: int) -> list:
    """This session's unique customer, shown only in its exports."""
    ctx = ledger.current()
    email = ledger.show("canary_customer", place)
    digest = bait.raw(ctx.bait_secret, ctx.session_id, "canary_customer", bait.PLACES[place])
    name = f"{FIRST_NAMES[digest[10] % len(FIRST_NAMES)]} {LAST_NAMES[digest[11] % len(LAST_NAMES)]}"
    joined = datetime.now().replace(microsecond=0) - timedelta(days=3 + digest[12] % 200)
    return [row_id, name, email, org_from_email(email), iso(joined), iso(joined + timedelta(days=1 + digest[13] % 3))]


def csv_line(values: list) -> str:
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerow(values)
    return buffer.getvalue()


async def stream_lines(rows: list[list], delay: float) -> AsyncIterator[str]:
    yield csv_line(COLUMNS)
    if not delay:
        yield "".join(csv_line(row) for row in rows)
        return
    for row in rows:
        await asyncio.sleep(delay)
        yield csv_line(row)


def customers_csv(db: Session, place: str, filename: str) -> StreamingResponse:
    users = list(db.scalars(select(User).where(User.role == "customer").order_by(User.id)))
    ctx = ledger.current()
    ctx.add_records("user", [user.id for user in users])
    rows = [[u.id, u.name, u.email, u.org, iso(u.created_at), iso(u.last_login)] for u in users]
    rows.append(visitor_row(place, (users[-1].id if users else 0) + 1))
    delay = 1 / ctx.drip_rate if ctx.dripping else 0.0
    return StreamingResponse(
        stream_lines(rows, delay),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
