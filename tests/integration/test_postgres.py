"""PostgreSQL persistence test.

Runs only when ``AGENTEVALOPS_TEST_POSTGRES_URL`` points at a reachable
Postgres instance (e.g. ``docker compose up -d postgres`` then
``export AGENTEVALOPS_TEST_POSTGRES_URL=postgresql+psycopg://agentevalops:agentevalops@localhost:5432/agentevalops``).
Skipped otherwise so the offline CI stays green.
"""

from __future__ import annotations

import os

import pytest

from agentevalops.persistence import get_store
from agentevalops.schemas.grading import GradingResult

URL = os.environ.get("AGENTEVALOPS_TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(not URL, reason="AGENTEVALOPS_TEST_POSTGRES_URL not set")


def test_postgres_migrations_and_roundtrip() -> None:
    assert URL is not None
    store = get_store(URL)
    g1 = GradingResult(trial_id="pg1", run_id="r1", instance_id="i1", model_id="m", behavior_id="b", grader_version="v1")
    g2 = GradingResult(trial_id="pg1", run_id="r1", instance_id="i1", model_id="m", behavior_id="b", grader_version="v2")
    store.save_grading(g1)
    store.save_grading(g2)
    loaded = store.get_gradings("r1")
    assert len(loaded) == 1
    assert loaded[0].grader_version == "v2"
