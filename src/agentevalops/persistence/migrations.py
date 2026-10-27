"""Minimal schema migration runner.

A lightweight, dependency-free alternative to Alembic: ordered migration
functions are applied in a transaction and recorded in ``schema_migrations``.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine

Migration = Callable[[Engine], None]


def migration_001(engine: Engine) -> None:
    from agentevalops.persistence import models  # noqa: F401
    from agentevalops.persistence.db import Base

    Base.metadata.create_all(engine)


MIGRATIONS: list[tuple[int, str, Migration]] = [
    (1, "baseline", migration_001),
]


def migrate(engine: Engine) -> list[int]:
    """Apply pending migrations, returning the versions that were applied."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version INTEGER PRIMARY KEY, name VARCHAR(128), applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
        )
    applied: list[int] = []
    for version, name, fn in MIGRATIONS:
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT 1 FROM schema_migrations WHERE version = :v"), {"v": version}
            ).first()
        if row is not None:
            continue
        fn(engine)
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO schema_migrations (version, name) VALUES (:v, :n)"),
                {"v": version, "n": name},
            )
        applied.append(version)
    return applied
