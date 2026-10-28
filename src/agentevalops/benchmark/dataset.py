"""Benchmark dataset persistence (JSONL + manifest)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agentevalops.schemas.benchmark import BenchmarkDataset, BenchmarkInstance


class DatasetManifest(BaseModel):
    benchmark_id: str
    dataset_version: str
    instance_count: int = 0
    behavior_ids: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    source_type: str = "synthetic"
    # SHA-256 of the instances.jsonl payload, for reproducibility/verification.
    checksum: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DatasetManager:
    def __init__(self, benchmark_root: str | Path = "datasets") -> None:
        self.root = Path(benchmark_root)

    def dataset_dir(self, benchmark_id: str, dataset_version: str) -> Path:
        return self.root / "synthetic" / f"{benchmark_id}__{dataset_version}"

    def save(self, dataset: BenchmarkDataset, source_type: str = "synthetic") -> Path:
        d = self.dataset_dir(dataset.benchmark_id, dataset.dataset_version)
        d.mkdir(parents=True, exist_ok=True)
        instances_path = d / "instances.jsonl"
        payload = "\n".join(i.model_dump_json() for i in dataset.instances)
        with instances_path.open("w", encoding="utf-8") as f:
            f.write(payload + ("\n" if payload else ""))
        manifest = DatasetManifest(
            benchmark_id=dataset.benchmark_id,
            dataset_version=dataset.dataset_version,
            instance_count=len(dataset.instances),
            behavior_ids=sorted({i.behavior_id for i in dataset.instances}),
            created_at=datetime.now(timezone.utc),
            source_type=source_type,
            checksum=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            metadata=dataset.metadata,
        )
        (d / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        return d

    def load(self, benchmark_id: str, dataset_version: str) -> BenchmarkDataset:
        d = self.dataset_dir(benchmark_id, dataset_version)
        return self.load_path(d / "instances.jsonl", benchmark_id, dataset_version)

    def load_path(
        self, path: str | Path, benchmark_id: str | None = None, dataset_version: str | None = None
    ) -> BenchmarkDataset:
        path = Path(path)
        instances: list[BenchmarkInstance] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            instances.append(BenchmarkInstance.model_validate_json(line))
        if not instances:
            return BenchmarkDataset(
                benchmark_id=benchmark_id or "unknown",
                dataset_version=dataset_version or "v1",
                instances=[],
            )
        return BenchmarkDataset(
            benchmark_id=benchmark_id or instances[0].benchmark_id,
            dataset_version=dataset_version or instances[0].dataset_version,
            instances=instances,
        )

    def to_jsonl(self, dataset: BenchmarkDataset) -> str:
        return "\n".join(i.model_dump_json() for i in dataset.instances)

    def manifest(self, benchmark_id: str, dataset_version: str) -> DatasetManifest | None:
        path = self.dataset_dir(benchmark_id, dataset_version) / "manifest.json"
        if not path.exists():
            return None
        return DatasetManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))
