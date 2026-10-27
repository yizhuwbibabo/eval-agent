"""Candidate confirmation interface.

Confirmation is separate from grading and from anchor recall. Its result is
stored separately from the final model grading result.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from agentevalops.schemas.behavior import BehaviorSpecification
from agentevalops.schemas.benchmark import Candidate, ConfirmationResult
from agentevalops.schemas.trace import Trace


class Confirmer(ABC):
    name: str = "base"
    version: str = "1.0"

    @abstractmethod
    def confirm(
        self, trace: Trace, behavior: BehaviorSpecification, candidate: Candidate
    ) -> ConfirmationResult:
        """Confirm whether the candidate decision point actually exhibits the target behavior."""

    async def aconfirm(
        self, trace: Trace, behavior: BehaviorSpecification, candidate: Candidate
    ) -> ConfirmationResult:
        """Async variant; defaults to the sync implementation."""
        return self.confirm(trace, behavior, candidate)
