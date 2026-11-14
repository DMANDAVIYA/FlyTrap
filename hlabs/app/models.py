"""Tables (spec 5.2). Naive UTC datetimes everywhere so SQLite and Postgres match."""

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    org: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), default="customer")  # customer | admin
    password_hash: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    session_version: Mapped[int] = mapped_column(Integer, default=0)


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True)
    label: Mapped[str] = mapped_column(String(80))
    scopes: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class HostedModel(Base):
    __tablename__ = "models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    size_gb: Mapped[float] = mapped_column(Float)
    visibility: Mapped[str] = mapped_column(String(20))  # public | private
    downloads: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    period: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    amount_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10))  # paid | due | overdue
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Usage(Base):
    __tablename__ = "usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[date] = mapped_column(Date)
    requests: Mapped[int] = mapped_column(Integer)
    tokens: Mapped[int] = mapped_column(BigInteger)


class Planted(Base):
    """Values planted for one visitor session through /_edge/plant (pods only)."""

    __tablename__ = "planted"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    value: Mapped[str] = mapped_column(String(200))
    place: Mapped[str] = mapped_column(String(40))  # account | api_keys | env | backup-01 | model-vault
    created_at: Mapped[datetime] = mapped_column(DateTime)
