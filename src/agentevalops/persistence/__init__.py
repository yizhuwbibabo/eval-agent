"""Persistence layer."""

from agentevalops.persistence.db import Base, Database, create_engine_from_url
from agentevalops.persistence.migrations import MIGRATIONS, migrate
from agentevalops.persistence.repositories import Store

__all__ = ["Base", "Database", "MIGRATIONS", "Store", "create_engine_from_url", "migrate"]


def get_store(database_url: str) -> Store:
    db = Database(database_url)
    migrate(db.engine)
    return Store(db)
