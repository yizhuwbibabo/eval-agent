"""Grading schemas: deterministic hits, rubric verdicts, hybrid verdicts."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    event_id: str | None = None
    description: str


class DeterministicHit(BaseModel):
    rule_id: str
    matched: bool
    evidence_event_ids: list[str] = Field(default_factory=list)
    message: str = ""
    severity: str = "info"  # info | warning | critical
    metadata: dict[str, Any] = Field(default_factory=dict)


class GradeStatus(str, Enum):
    GRADED = "graded"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    ERROR = "error"
    UNSUPPORTED = "unsupported"


class GraderVerdict(BaseModel):
    grader_id: str
    grader_version: str
    score: float | None = None  # 0..5
    passed: bool | None = None
    violated_criteria: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    reason: str = ""
    status: GradeStatus = GradeStatus.GRADED
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HybridVerdict(BaseModel):
    final_score: float | None = None
    passed: bool | None = None
    strategy: str
    components: list[GraderVerdict] = Field(default_factory=list)
    # Rule id of a hard-constraint hit that forced the final verdict to FAIL
    # regardless of semantic score.
    overridden_by: str | None = None
    status: GradeStatus = GradeStatus.GRADED


class GradingResult(BaseModel):
    """Full grading outcome for one trial, kept separate from confirmation."""

    trial_id: str
    run_id: str
    instance_id: str
    model_id: str
    behavior_id: str
    deterministic_hits: list[DeterministicHit] = Field(default_factory=list)
    rubric_verdict: GraderVerdict | None = None
    hybrid: HybridVerdict | None = None
    grader_version: str = "v1"
