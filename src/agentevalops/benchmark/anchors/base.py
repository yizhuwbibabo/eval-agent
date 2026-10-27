"""Anchor interface.

Anchors are responsible for *recall only*: scanning a structured trace and
returning candidate decision points. They must never make the final semantic
confirmation (that is the confirmation layer's job).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from agentevalops.schemas.behavior import BehaviorSpecification
from agentevalops.schemas.benchmark import Candidate
from agentevalops.schemas.trace import Trace


class Anchor(ABC):
    name: str = "base"
    version: str = "1.0"

    @abstractmethod
    def scan(self, trace: Trace, behavior: BehaviorSpecification) -> list[Candidate]:
        """Return candidate decision points (recall)."""

    # -- helpers ------------------------------------------------------------ #
    def _candidate(
        self,
        trace: Trace,
        behavior: BehaviorSpecification,
        cut_event_id: str,
        evidence_event_ids: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> Candidate:
        return Candidate(
            candidate_id=f"{trace.trace_id}:{self.name}:{cut_event_id}",
            behavior_id=behavior.behavior_id,
            source_trace_id=trace.trace_id,
            cut_event_id=cut_event_id,
            anchor_name=self.name,
            anchor_version=self.version,
            evidence_event_ids=evidence_event_ids,
            metadata=metadata or {},
        )

    def _context_filter_passes(self, trace: Trace, behavior: BehaviorSpecification) -> bool:
        """Optional context filters from anchor params (e.g. source_system)."""
        params = behavior.anchor_definition.params
        filters = params.get("context_filter") or {}
        if not filters:
            return True
        for key, allowed in filters.items():
            if key == "source_system":
                if isinstance(allowed, list) and trace.source_system not in allowed:
                    return False
            if key == "source_model":
                if isinstance(allowed, list) and trace.source_model not in allowed:
                    return False
        return True
