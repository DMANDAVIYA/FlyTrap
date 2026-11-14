"""Deterministic customer generator.

Keep this file byte-identical with islands/people.py: backup-01 serves a
customer CSV whose rows must match what the admin panel shows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from faker import Faker

COMPANY_SUFFIX = ["labs", "robotics", "analytics", "systems", "health", "bio", "logistics", "ai", "data", "works"]
EPOCH = datetime(2026, 11, 13, 9, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class Person:
    id: int
    first: str
    last: str
    email: str
    org: str
    plan: str
    created_at: datetime

    @property
    def name(self) -> str:
        return f"{self.first} {self.last}"


def _slug(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())[:18] or "co"


def people(seed: int, count: int, first_id: int = 1) -> list[Person]:
    """Same seed + count -> same people, on every machine (pinned Faker version)."""
    fake = Faker("en_US")
    fake.seed_instance(seed)
    out: list[Person] = []
    seen: set[str] = set()
    for i in range(count):
        first, last = fake.first_name(), fake.last_name()
        org_word = fake.last_name()
        suffix = COMPANY_SUFFIX[fake.random_int(0, len(COMPANY_SUFFIX) - 1)]
        org = f"{org_word} {suffix.title() if suffix != 'ai' else 'AI'}"
        domain = f"{_slug(org_word)}-{suffix}.example"
        email = f"{_slug(first)}.{_slug(last)}@{domain}"
        if email in seen:
            email = f"{_slug(first)}.{_slug(last)}{i}@{domain}"
        seen.add(email)
        # Denser recently: square the uniform draw so more accounts are young.
        age_days = int((fake.random_int(0, 1000) / 1000) ** 2 * 540)
        created = EPOCH - timedelta(days=age_days, minutes=fake.random_int(0, 1440))
        plan = ["Starter", "Team", "Team", "Scale", "Enterprise"][fake.random_int(0, 4)]
        out.append(Person(first_id + i, first, last, email, org, plan, created))
    return out


def csv_rows(seed: int, count: int) -> list[list[str]]:
    rows = [["id", "name", "email", "company", "plan", "created_at"]]
    for p in people(seed, count):
        rows.append([str(p.id), p.name, p.email, p.org, p.plan, p.created_at.strftime("%Y-%m-%d")])
    return rows
