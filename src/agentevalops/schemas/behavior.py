"""Behavior specification schema.

Behaviors are versioned and decoupled from any specific model invocation.
The ``cut_contract`` defines how a decision point is carved out of a trace and
what must never leak to the model under test.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class BehaviorFrame(str, Enum):
    ACTION = "ACTION"
    FAILURE = "FAILURE"
    CLAIM = "CLAIM"


class CutMode(str, Enum):
    ACTION = "ACTION"
    FAILURE = "FAILURE"
    CLAIM = "CLAIM"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RubricCriterion(BaseModel):
    criterion_id: str
    description: str
    weight: float = 1.0


class Rubric(BaseModel):
    rubric_id: str
    version: str
    description: str = ""
    criteria: list[RubricCriterion] = Field(default_factory=list)
    # Score (0-5) at or above which the behavior is considered to have passed.
    pass_threshold: float = 4.0


class AnchorDefinition(BaseModel):
    anchor_type: str
    params: dict[str, Any] = Field(default_factory=dict)


class ConfirmationCriteria(BaseModel):
    description: str = ""
    required_evidence_min: int = 1


class CutContract(BaseModel):
    mode: CutMode
    # Number of trailing context events to retain before the cut point.
    context_events: int = 6
    drop_target_response: bool = True


class BehaviorSpecification(BaseModel):
    behavior_id: str
    name: str
    description: str
    behavior_frame: BehaviorFrame
    anchor_definition: AnchorDefinition
    confirmation_criteria: ConfirmationCriteria = Field(default_factory=ConfirmationCriteria)
    cut_contract: CutContract
    rubric: Rubric
    severity: Severity = Severity.MEDIUM
    specification_version: str
    metadata: dict[str, Any] = Field(default_factory=dict)
