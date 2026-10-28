"""Persistence: SQLAlchemy engine/session setup."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def create_engine_from_url(url: str) -> Engine:
    if url.startswith("sqlite"):
        # SQLite does not create parent directories; ensure they exist.
        if "sqlite:///" in url:
            db_path = url.split("sqlite:///", 1)[-1]
            if db_path and db_path != ":memory:" and not db_path.startswith("file:"):
                from pathlib import Path

                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False}, future=True)
        # WAL + relaxed synchronous trades a small amount of durability for
        # dramatically lower write latency under per-trial checkpoint commits,
        # while remaining crash-safe for a single-process evaluator.
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _record) -> None:  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

        return engine
    return create_engine(url, future=True, pool_pre_ping=True)


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self.engine = create_engine_from_url(url)
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def session(self) -> Session:
        return self._session_factory()

    def create_schema(self) -> None:
        from agentevalops.persistence import models  # noqa: F401 - register tables

        Base.metadata.create_all(self.engine)
