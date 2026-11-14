"""Generate the company's data. Never calls a model; texts come from seed/texts.json.

  python -m app.seed --role real                      # seeds DATABASE_URL once (idempotent, locked)
  python -m app.seed --role pod --out /templates/pod.db  # builds the template copied into each instance
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import secrets
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from . import people as ppl
from .bait import B62, demo_password
from .models import ApiToken, Base, Invoice, Model, Planted, Usage, User, make_engine

TEXTS = json.loads((Path(__file__).resolve().parent.parent / "seed" / "texts.json").read_text())
DEMO_EMAIL = "demo@valley-robotics.example"
PROFILES = {
    # role: (faker seed, users, tokens, models, invoices, first user id)
    "real": (7, 200, 400, 40, 1000, 2001),
    "pod": (1001, 500, 1200, 80, 3000, 1),
}


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 1000).hex()
    return f"pbkdf2${salt}${digest}"


def check_password(password: str, stored: str) -> bool:
    try:
        _, salt, _ = stored.split("$")
    except ValueError:
        return False
    return secrets.compare_digest(hash_password(password, salt), stored)


def _token(rng: random.Random) -> str:
    return "hl_live_" + "".join(rng.choice(B62) for _ in range(24))


def build(session: Session, role: str) -> None:
    seed, n_users, n_tokens, n_models, n_invoices, first_id = PROFILES[role]
    rng = random.Random(seed)
    persons = ppl.people(seed, n_users, first_id)
    users = [User(id=p.id, email=p.email, name=p.name, org=p.org, plan=p.plan, role="customer",
                  password_hash=hash_password(secrets.token_urlsafe(12), f"s{p.id}"), created_at=p.created_at)
             for p in persons]
    users.append(User(id=first_id - 1 if first_id > 1 else n_users + 1, email="ops@hackumass-labs.example",
                      name="Platform Ops", org="HackUMass Labs", plan="Internal", role="admin",
                      password_hash=hash_password(secrets.token_urlsafe(24)), created_at=ppl.EPOCH - timedelta(days=600)))
    session.add_all(users)
    session.flush()
    customers = [u for u in users if u.role == "customer"]

    for i in range(n_tokens):
        u = customers[i % len(customers)] if i < len(customers) else rng.choice(customers)
        session.add(ApiToken(user_id=u.id, token=_token(rng), label=rng.choice(TEXTS["token_labels"]),
                             scopes=rng.choice(["models:read", "models:read,models:write", "inference", "billing:read"]),
                             created_at=u.created_at + timedelta(days=rng.randint(0, 60))))

    names = set()
    for i in range(n_models):
        while True:
            name = f"{rng.choice(TEXTS['model_prefixes'])}-{rng.choice(TEXTS['model_kinds'])}"
            if name not in names:
                break
            name = f"{name}-v{rng.randint(2, 9)}"
            if name not in names:
                break
        names.add(name)
        owner = rng.choice(customers)
        session.add(Model(owner_id=owner.id, name=name, slug=name.lower(), size_gb=round(rng.uniform(0.3, 48), 1),
                          visibility="public" if i % 3 else "private", downloads=rng.randint(12, 48000),
                          description=rng.choice(TEXTS["model_descriptions"]),
                          created_at=ppl.EPOCH - timedelta(days=rng.randint(1, 500))))

    start_id = 9001 if role == "real" else 1001
    for i in range(n_invoices):
        u = rng.choice(customers)
        months_ago = int(rng.random() ** 1.6 * 18)
        d = date(2026, 11, 1) - timedelta(days=30 * months_ago)
        status = "paid" if months_ago > 1 else rng.choice(["paid", "paid", "due", "overdue"])
        session.add(Invoice(id=start_id + i, user_id=u.id, period=d.strftime("%Y-%m"),
                            amount_cents=rng.choice([4900, 19900, 49900, 129900]) + rng.randint(0, 40000),
                            status=status, created_at=ppl.EPOCH - timedelta(days=30 * months_ago)))

    for u in customers[:60]:
        for d in range(14):
            session.add(Usage(user_id=u.id, day=date(2026, 11, 13) - timedelta(days=d),
                              requests=rng.randint(40, 9000), tokens=rng.randint(10_000, 4_000_000)))


def add_demo_customer(session: Session) -> None:
    """The one known real-side customer (Sisyphus and Odysseus log in with it)."""
    if session.scalar(select(User).where(User.email == DEMO_EMAIL)):
        return
    demo = User(id=2042 + 1000, email=DEMO_EMAIL, name="Dana Whitfield", org="Valley Robotics", plan="Team",
                role="customer", password_hash=hash_password(demo_password()), created_at=ppl.EPOCH - timedelta(days=210))
    session.add(demo)
    session.flush()
    rng = random.Random(42)
    session.add(ApiToken(user_id=demo.id, token=_token(rng), label="ci-pipeline", scopes="models:read,inference"))
    session.add(ApiToken(user_id=demo.id, token=_token(rng), label="notebook", scopes="models:read"))
    for m in range(6):
        d = date(2026, 11, 1) - timedelta(days=30 * m)
        session.add(Invoice(id=8001 + m, user_id=demo.id, period=d.strftime("%Y-%m"), amount_cents=19900 + 1250 * m,
                            status="due" if m == 0 else "paid", created_at=ppl.EPOCH - timedelta(days=30 * m)))


def seed_real(url: str | None = None) -> None:
    engine = make_engine(url)
    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(4242)"))   # web-1 and web-2 start together
        Base.metadata.create_all(conn)
        with Session(bind=conn) as s:
            if not s.scalar(select(func.count()).select_from(User)):
                build(s, "real")
            add_demo_customer(s)
            s.flush()
        if conn.dialect.name == "postgresql":
            for table in ("users", "api_tokens", "models", "invoices", "usage", "planted"):
                conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                                  f"(SELECT COALESCE(max(id), 1) FROM {table}))"))


def seed_template(out: str) -> None:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    engine = make_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    with Session(engine) as s, s.begin():
        build(s, "pod")
    _ = Planted  # created with the schema
    engine.dispose()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=["real", "pod"], required=True)
    ap.add_argument("--out", default="/templates/pod.db")
    args = ap.parse_args()
    if args.role == "pod":
        seed_template(args.out)
    else:
        seed_real()
    print(f"seeded {args.role}")
