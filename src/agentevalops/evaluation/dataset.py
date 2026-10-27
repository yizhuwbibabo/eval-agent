"""Evaluation dataset manager (loads built benchmark datasets for a run)."""

from __future__ import annotations

from pathlib import Path

from agentevalops.benchmark.dataset import DatasetManager
from agentevalops.schemas.benchmark import BenchmarkDataset

__all__ = ["DatasetManager", "load_dataset_for_run"]


def load_dataset_for_run(
    dataset_id: str,
    dataset_version: str,
    dataset_path: str | None,
    benchmark_root: str | Path = "datasets",
) -> BenchmarkDataset:
    manager = DatasetManager(benchmark_root)
    if dataset_path:
        return manager.load_path(dataset_path, dataset_id, dataset_version)
    return manager.load(dataset_id, dataset_version)
