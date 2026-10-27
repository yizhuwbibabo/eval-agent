"""Benchmark dataset, instance and construction-artifact schemas.

The schema keeps the distinct entities - raw trace, candidate, confirmed
occurrence, benchmark instance, model response and grading result - in separate
typed objects instead of one unstructured JSON blob.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from agentevalops.schemas.behavior import BehaviorFrame

# --------------------------------------------------------------------------- #
# Construction artifacts
# --------------------------------------------------------------------------- #


class Candidate(BaseModel):
    """A candidate decision point produced by an anchor (recall only)."""

    candidate_id: str
    behavior_id: str
    source_trace_id: str
    cut_event_id: str
    anchor_name: str
    anchor_version: str
    evidence_event_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConfirmationStatus(str, Enum):
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNSUPPORTED = "unsupported"
    ERROR = "error"


class ConfirmationResult(BaseModel):
    candidate_id: str
    is_valid: bool
    target_behavior_observed: bool
    context_sufficient: bool
    decision_already_made: bool
    evidence_event_ids: list[str] = Field(default_factory=list)
    reason: str
    status: ConfirmationStatus
    judge_id: str
    judge_version: str
    confidence: float | None = None

    @property
    def confirmed(self) -> bool:
        return self.status == ConfirmationStatus.CONFIRMED


# --------------------------------------------------------------------------- #
# Benchmark instances
# --------------------------------------------------------------------------- #


class InstanceStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    QUARANTINED = "quarantined"


class ContextMessage(BaseModel):
    """One message of the rendered context given to the model under test."""

    role: str
    content: str | None = None
    tool_name: str | None = None
    tool_call_id: str | None = None
    tool_arguments: dict[str, Any] | None = None
    tool_result: Any = None
    error: str | None = None
    event_id: str | None = None


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class BenchmarkInstance(BaseModel):
    benchmark_id: str
    dataset_version: str
    instance_id: str
    behavior_id: str
    frame: BehaviorFrame
    source_trace_id: str
    cut_event_id: str
    context: list[ContextMessage] = Field(default_factory=list)
    tool_definitions: list[ToolDefinition] = Field(default_factory=list)
    rubric_id: str
    rubric_version: str
    # Evidence events referenced for audit only - never shown to the model.
    evidence_references: list[str] = Field(default_factory=list)
    # Structured metadata used by deterministic graders and mock providers.
    cut_metadata: dict[str, Any] = Field(default_factory=dict)
    validation_status: InstanceStatus = InstanceStatus.VALID
    source_type: str = "synthetic"  # synthetic | production
    created_at: datetime | None = None


class BenchmarkDataset(BaseModel):
    benchmark_id: str
    dataset_version: str
    instances: list[BenchmarkInstance] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
