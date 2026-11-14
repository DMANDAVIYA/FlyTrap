"""Engine and sessions. Pods can swap their SQLite file for the template copy."""

import os
import shutil
from collections.abc import Iterator
from pathlib import Path

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False, "timeout": 10})
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)


class Database:
    def __init__(self, url: str) -> None:
        self.engine = make_engine(url)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def session(self) -> Session:
        return self.sessions()

    def create_tables(self) -> None:
        Base.metadata.create_all(self.engine)

    def sqlite_path(self) -> Path:
        database = self.engine.url.database
        if self.engine.dialect.name != "sqlite" or not database:
            raise RuntimeError("only file-based SQLite databases can be restored")
        return Path(database)

    def restore(self, template: Path) -> None:
        """Replace the live SQLite file with a fresh copy of the template."""
        live = self.sqlite_path()
        staging = live.with_suffix(".restore")
        shutil.copyfile(template, staging)
        self.engine.dispose()
        os.replace(staging, live)
        self.engine.dispose()

    def ensure_copy_of(self, template: Path) -> None:
        live = self.sqlite_path()
        if not live.exists():
            live.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(template, live)


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.db.session() as session:
        yield session
