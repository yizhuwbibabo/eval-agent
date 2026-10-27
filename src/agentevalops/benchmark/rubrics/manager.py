"""Rubric management.

Rubrics are versioned and resolved per behavior. A grader always records the
rubric version it used so that old responses can be re-scored against a new
rubric version.
"""

from __future__ import annotations

from agentevalops.benchmark.registry import BehaviorRegistry
from agentevalops.schemas.behavior import Rubric


class RubricManager:
    def __init__(self, registry: BehaviorRegistry) -> None:
        self.registry = registry

    def get_rubric(self, behavior_id: str, version: str | None = None) -> Rubric:
        behavior = self.registry.get(behavior_id)
        rubric = behavior.rubric
        if version is not None and rubric.version != version:
            raise KeyError(
                f"rubric version {version!r} not found for behavior {behavior_id!r} "
                f"(available: {rubric.version!r})"
            )
        return rubric

    def rubric_version(self, behavior_id: str) -> str:
        return self.registry.get(behavior_id).rubric.version
