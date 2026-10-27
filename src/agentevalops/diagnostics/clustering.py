"""Basic failure clustering over verified, structured attributes.

Clustering keys are stable identifiers (behavior, category, rule, tool, error
code) - never unverified semantic similarity. Embedding-based clustering is an
explicitly optional future extension.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field

from agentevalops.schemas.diagnosis import FailureDiagnosis


class Cluster(BaseModel):
    key: str
    dimension: str
    count: int = 0
    diagnosis_ids: list[str] = Field(default_factory=list)
    label: dict[str, Any] = Field(default_factory=dict)


class ClusteringResult(BaseModel):
    clusters: list[Cluster] = Field(default_factory=list)
    total: int = 0


DIMENSIONS = ["behavior_id", "primary_category", "model_id"]


def cluster(diagnoses: list[FailureDiagnosis], dimensions: list[str] | None = None) -> ClusteringResult:
    dims = dimensions or DIMENSIONS
    buckets: dict[str, Cluster] = {}
    for d in diagnoses:
        key_parts = []
        label: dict[str, Any] = {}
        for dim in dims:
            value = getattr(d, dim, None)
            key_parts.append(str(value))
            label[dim] = value
        key = "|".join(key_parts)
        if key not in buckets:
            buckets[key] = Cluster(key=key, dimension="+".join(dims), label=label)
        buckets[key].count += 1
        buckets[key].diagnosis_ids.append(d.diagnosis_id)
    clusters = sorted(buckets.values(), key=lambda c: -c.count)
    return ClusteringResult(clusters=clusters, total=len(diagnoses))


def failure_distribution(diagnoses: list[FailureDiagnosis]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for d in diagnoses:
        counts[d.primary_category.value] += 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))
