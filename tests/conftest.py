"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentevalops.benchmark.builder import BenchmarkBuilder
from agentevalops.benchmark.registry import BehaviorRegistry
from agentevalops.datagen import generate_all
from agentevalops.schemas.benchmark import BenchmarkInstance

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def registry() -> BehaviorRegistry:
    return BehaviorRegistry.from_dir(REPO_ROOT / "configs" / "behaviors")


@pytest.fixture(scope="session")
def traces():
    return generate_all()


@pytest.fixture(scope="session")
def instances(registry, traces) -> dict[str, BenchmarkInstance]:
    builder = BenchmarkBuilder(registry)
    out: dict[str, BenchmarkInstance] = {}
    for bid in registry.ids():
        result = builder.build(traces, bid, "test", "v1")
        for inst in result.dataset.instances:
            out[inst.instance_id] = inst
    return out


@pytest.fixture(scope="session")
def instance_list(instances) -> list[BenchmarkInstance]:
    return list(instances.values())
