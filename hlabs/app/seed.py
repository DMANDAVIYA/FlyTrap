"""Generated data (spec 5.2). Deterministic: Faker and random share one seed.

    python -m app.seed --role pod --seed 1001 --out /templates/pod.db

Emails only under .example domains; model names come from word lists.
"""

import argparse
import json
import random
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from time import sleep

from faker import Faker
from sqlalchemy import func, insert, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.bait import ALPHABET
from app.db import Database
from app.models import ApiToken, Base, HostedModel, Invoice, Usage, User
from app.words import is_clean

TEXTS = json.loads((Path(__file__).parent / "seed" / "texts.json").read_text(encoding="utf-8"))
SEED_LOCK_KEY = 7_001_001
DEMO_EMAIL = "demo@valley-robotics.example"
STAFF_DOMAIN = "hackumass-labs.example"
STAFF = ("Maya Okafor", "Jonah Reyes", "Priya Raman")
UNUSABLE_PASSWORD = "!"  # matches no password
HISTORY_DAYS = 540  # 18 months
USAGE_DAYS = 30
FIRST_INVOICE_ID = 9001


@dataclass(frozen=True)
class Counts:
    users: int
    tokens: int
    models: int
    invoices: int


COUNTS = {"real": Counts(200, 400, 40, 1000), "pod": Counts(500, 1200, 80, 3000)}


@dataclass
class SeedData:
    users: list[dict] = field(default_factory=list)
    tokens: list[dict] = field(default_factory=list)
    models: list[dict] = field(default_factory=list)
    invoices: list[dict] = field(default_factory=list)
    usage: list[dict] = field(default_factory=list)


class Generator:
    def __init__(self, seed: int, today: date) -> None:
        self.fake = Faker("en_US")
        self.fake.seed_instance(seed)
        self.rng = random.Random(seed)
        self.today = today
        self.now = datetime.combine(today, time(12, 0))

    def clean(self, make: Callable[[], str]) -> str:
        while not is_clean(value := make()):
            pass
        return value

    def past(self, max_days: int = HISTORY_DAYS) -> datetime:
        """A moment in the last max_days, denser towards today."""
        days = max_days * self.rng.random() ** 2
        return self.now - timedelta(days=days, seconds=self.rng.randint(0, 86_399))

    def between(self, start: datetime, end: datetime) -> datetime:
        span = max((end - start).total_seconds(), 0)
        return start + timedelta(seconds=self.rng.uniform(0, span))

    def token(self) -> str:
        return "hl_live_" + "".join(self.rng.choice(ALPHABET) for _ in range(24))


def slug(text_value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text_value.lower()).strip("-")


def org_from_email(email: str) -> str:
    domain = email.partition("@")[2].removesuffix(".example")
    return " ".join(part.capitalize() for part in domain.split("-")) or "Personal"


def number(rows: list[dict], start: int = 1) -> list[dict]:
    for offset, row in enumerate(rows):
        row["id"] = start + offset
    return rows


# --- users ---------------------------------------------------------------------


def user_row(email: str, name: str, org: str, role: str, created: datetime, last_login: datetime) -> dict:
    return {
        "email": email,
        "name": name,
        "org": org,
        "role": role,
        "password_hash": UNUSABLE_PASSWORD,
        "created_at": created,
        "last_login": last_login,
        "session_version": 0,
    }


def build_users(gen: Generator, count: int) -> list[dict]:
    demo = user_row(DEMO_EMAIL, "Dana Whitfield", "Valley Robotics", "customer",
                    gen.now - timedelta(days=420), gen.now - timedelta(hours=20))
    staff = [
        user_row(f"{slug(name).replace('-', '.')}@{STAFF_DOMAIN}", name, "HackUMass Labs", "admin",
                 gen.now - timedelta(days=HISTORY_DAYS + index), gen.now - timedelta(hours=2 + index))
        for index, name in enumerate(STAFF)
    ]
    orgs = [gen.clean(gen.fake.company) for _ in range(max(count // 3, 1))]
    seen = {demo["email"], *(row["email"] for row in staff)}
    customers: list[dict] = []
    while len(customers) < count - 1 - len(staff):
        first, last = gen.clean(gen.fake.first_name), gen.clean(gen.fake.last_name)
        org = gen.rng.choice(orgs)
        email = f"{slug(first)}.{slug(last)}@{slug(org)}.example"
        if email in seen:
            continue
        seen.add(email)
        created = gen.past()
        customers.append(user_row(email, f"{first} {last}", org, "customer", created, gen.between(created, gen.now)))
    customers.sort(key=lambda row: row["created_at"])
    return number([demo, *staff, *customers])


# --- tokens, models, invoices, usage ---------------------------------------------


def token_row(gen: Generator, user: dict, label: str | None = None, scopes: str | None = None) -> dict:
    created = gen.between(user["created_at"], gen.now)
    return {
        "user_id": user["id"],
        "token": gen.clean(gen.token),
        "label": label or gen.rng.choice(TEXTS["token_labels"]),
        "scopes": scopes or gen.rng.choice(TEXTS["token_scopes"]),
        "created_at": created,
        "last_used_at": None if gen.rng.random() < 0.2 else gen.between(created, gen.now),
        "revoked_at": None,
    }


def build_tokens(gen: Generator, users: list[dict], count: int) -> list[dict]:
    demo, customers = users[0], [u for u in users if u["role"] == "customer"]
    rows = [token_row(gen, demo, "Production", "inference models:read"),
            token_row(gen, demo, "CI pipeline", "models:read models:write")]
    rows += [token_row(gen, gen.rng.choice(customers)) for _ in range(count - len(rows))]
    return number(sorted(rows, key=lambda row: row["created_at"]))


def build_models(gen: Generator, users: list[dict], count: int) -> list[dict]:
    customers = [u for u in users if u["role"] == "customer"]
    descriptions: dict[str, list[str]] = TEXTS["model_descriptions"]
    rows, names = [], set()
    while len(rows) < count:
        suffix = gen.rng.choice(sorted(descriptions))
        params = gen.rng.choice(TEXTS["model_params"])
        name = f"{gen.rng.choice(TEXTS['model_prefixes'])}-{params}B-{suffix}"
        if name in names:
            continue
        names.add(name)
        owner = gen.rng.choice(customers)
        public = gen.rng.random() < 0.7
        rows.append({
            "owner_id": owner["id"],
            "name": name,
            "slug": slug(name),
            "size_gb": round(params * 2.02 * gen.rng.uniform(0.96, 1.04), 1),
            "visibility": "public" if public else "private",
            "downloads": int(gen.rng.paretovariate(1.3) * (140 if public else 6)),
            "description": gen.rng.choice(descriptions[suffix]),
            "created_at": gen.between(owner["created_at"], gen.now),
        })
    return number(sorted(rows, key=lambda row: row["created_at"]))


def billing_periods(today: date, months: int = 18) -> list[str]:
    """The `months` complete months before today, oldest first."""
    year, month = today.year, today.month
    periods = []
    for _ in range(months):
        year, month = (year - 1, 12) if month == 1 else (year, month - 1)
        periods.append(f"{year:04d}-{month:02d}")
    return periods[::-1]


def invoice_row(gen: Generator, user: dict, period: str, latest: str) -> dict:
    year, month = map(int, period.split("-"))
    issued = datetime(year + month // 12, month % 12 + 1, 1, 9, 0)
    roll = gen.rng.random()
    if period == latest:
        status = "paid" if roll < 0.75 else ("due" if roll < 0.95 else "overdue")
    else:
        status = "paid" if roll < 0.97 else "overdue"
    base = gen.rng.choice((4_900, 4_900, 14_900, 49_900))
    return {"user_id": user["id"], "period": period, "amount_cents": base + gen.rng.randint(0, 30_000),
            "status": status, "created_at": issued}


def build_invoices(gen: Generator, users: list[dict], count: int) -> list[dict]:
    periods = billing_periods(gen.today)
    demo, customers = users[0], [u for u in users if u["role"] == "customer"]
    rows = [invoice_row(gen, demo, period, periods[-1]) for period in periods[-12:]]
    taken = {(demo["id"], period) for period in periods[-12:]}
    while len(rows) < count:
        user = gen.rng.choice(customers)
        open_periods = [p for p in periods if p >= user["created_at"].strftime("%Y-%m")]
        period = gen.rng.choice(open_periods or periods[-1:])
        if (user["id"], period) in taken:
            continue
        taken.add((user["id"], period))
        rows.append(invoice_row(gen, user, period, periods[-1]))
    return number(sorted(rows, key=lambda row: (row["period"], row["user_id"])), FIRST_INVOICE_ID)


def build_usage(gen: Generator, users: list[dict]) -> list[dict]:
    rows = []
    for user in users:
        if user["role"] != "customer":
            continue
        daily = gen.rng.lognormvariate(6.0, 1.1)
        for back in range(USAGE_DAYS, 0, -1):
            day = gen.today - timedelta(days=back)
            if day < user["created_at"].date():
                continue
            weekend = 0.55 if day.weekday() >= 5 else 1.0
            growth = 1 + (USAGE_DAYS - back) * 0.012
            requests = int(daily * weekend * growth * gen.rng.uniform(0.7, 1.3))
            rows.append({"user_id": user["id"], "day": day, "requests": requests,
                         "tokens": requests * gen.rng.randint(300, 1400)})
    return number(rows)


def build(role: str, seed: int, today: date | None = None) -> SeedData:
    gen = Generator(seed, today or date.today())
    counts = COUNTS[role]
    users = build_users(gen, counts.users)
    return SeedData(
        users=users,
        tokens=build_tokens(gen, users, counts.tokens),
        models=build_models(gen, users, counts.models),
        invoices=build_invoices(gen, users, counts.invoices),
        usage=build_usage(gen, users),
    )


# --- writing -------------------------------------------------------------------


TABLES = ((User, "users"), (ApiToken, "tokens"), (HostedModel, "models"), (Invoice, "invoices"), (Usage, "usage"))


def write(session: Session, data: SeedData) -> None:
    for model, attr in TABLES:
        rows = getattr(data, attr)
        if rows:
            session.execute(insert(model), rows)
    if session.get_bind().dialect.name == "postgresql":
        # Rows were inserted with explicit ids; move each sequence past them.
        for model, _ in TABLES:
            table = model.__tablename__
            session.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), (SELECT MAX(id) FROM {table}))"
            ))


def seed_database(session: Session, role: str, seed: int) -> None:
    write(session, build(role, seed))


def seed_if_empty(database: Database, role: str, seed: int, attempts: int = 30) -> None:
    """Create tables and seed once. On Postgres an advisory lock makes replicas
    that start together take turns, so only the first one seeds."""
    for attempt in range(1, attempts + 1):
        try:
            with database.session() as session:
                if session.get_bind().dialect.name == "postgresql":
                    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": SEED_LOCK_KEY})
                Base.metadata.create_all(session.connection())
                if not session.scalar(select(func.count(User.id))):
                    seed_database(session, role, seed)
                session.commit()
            return
        except OperationalError:
            if attempt == attempts:
                raise
            sleep(1)


def build_sqlite(out: Path, role: str, seed: int) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    database = Database(f"sqlite:///{out.as_posix()}")
    database.create_tables()
    with database.session() as session:
        seed_database(session, role, seed)
        session.commit()
    database.engine.dispose()


# --- lazy accounts (pods) ------------------------------------------------------------


def adopt_user(db: Session, claims: dict) -> User:
    """Pods: make sure the user named by a valid login cookie exists here (spec 5.2)."""
    uid, email = int(claims["uid"]), str(claims.get("email", ""))
    name = str(claims.get("name") or email.partition("@")[0])
    user = db.get(User, uid)
    if user and user.email == email:
        return user
    same_email = db.scalar(select(User).where(User.email == email))
    if same_email:
        return same_email
    if user:
        user.email, user.name, user.org = email, name, org_from_email(email)
    else:
        user = add_user_with_history(db, uid, email, name)
    db.commit()
    return user


def add_user_with_history(db: Session, uid: int, email: str, name: str) -> User:
    gen = Generator(uid, date.today())
    created = gen.now - timedelta(days=gen.rng.randint(90, 400))
    user = User(**user_row(email, name, org_from_email(email), "customer", created, gen.now), id=uid)
    db.add(user)
    db.flush()
    row = {"id": uid, "role": "customer", "created_at": created}
    for item in (token_row(gen, row, "Production"), token_row(gen, row, "Local dev")):
        db.add(ApiToken(**item))
    periods = billing_periods(gen.today)
    for period in periods[-6:]:
        db.add(Invoice(**invoice_row(gen, row, period, periods[-1])))
    for item in build_usage(gen, [row]):
        item.pop("id")
        db.add(Usage(**item))
    return user


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build a seeded SQLite database.")
    parser.add_argument("--role", choices=sorted(COUNTS), required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    build_sqlite(args.out, args.role, args.seed)
    print(f"seeded {args.role} data (seed {args.seed}) into {args.out}")


if __name__ == "__main__":
    main()
