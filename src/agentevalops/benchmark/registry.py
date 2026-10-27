"""Behavior registry: loads versioned behavior specifications from YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agentevalops.schemas.behavior import BehaviorSpecification


class BehaviorRegistry:
    def __init__(self, specs: list[BehaviorSpecification]) -> None:
        self._specs: dict[str, BehaviorSpecification] = {}
        for spec in specs:
            self._specs[spec.behavior_id] = spec

    @classmethod
    def from_dir(cls, path: str | Path) -> BehaviorRegistry:
        specs: list[BehaviorSpecification] = []
        root = Path(path)
        for file in sorted(root.glob("*.yaml")) + sorted(root.glob("*.yml")):
            raw = yaml.safe_load(file.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                continue
            specs.append(BehaviorSpecification.model_validate(raw))
        return cls(specs)

    @classmethod
    def from_specs(cls, specs: list[BehaviorSpecification]) -> BehaviorRegistry:
        return cls(specs)

    def get(self, behavior_id: str) -> BehaviorSpecification:
        if behavior_id not in self._specs:
            raise KeyError(f"unknown behavior {behavior_id!r}; available: {sorted(self._specs)}")
        return self._specs[behavior_id]

    def all(self) -> list[BehaviorSpecification]:
        return list(self._specs.values())

    def ids(self) -> list[str]:
        return sorted(self._specs)

    def to_dicts(self) -> list[dict[str, Any]]:
        return [s.model_dump() for s in self.all()]
