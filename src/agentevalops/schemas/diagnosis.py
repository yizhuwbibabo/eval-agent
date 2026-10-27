"""Failure diagnosis schema.

Diagnoses separate what was observed from what is inferred or merely
hypothesized, and never fabricate a root cause. Evidence must reference real
events or grading artifacts.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FailureCategory(str, Enum):
    MODEL_BEHAVIOR_WRONG_TOOL_SELECTION = "MODEL_BEHAVIOR.WRONG_TOOL_SELECTION"
    MODEL_BEHAVIOR_INVALID_TOOL_ARGUMENTS = "MODEL_BEHAVIOR.INVALID_TOOL_ARGUMENTS"
    MODEL_BEHAVIOR_INSTRUCTION_VIOLATION = "MODEL_BEHAVIOR.INSTRUCTION_VIOLATION"
    MODEL_BEHAVIOR_ERROR_RECOVERY_FAILURE = "MODEL_BEHAVIOR.ERROR_RECOVERY_FAILURE"
    MODEL_BEHAVIOR_MISSING_PREREQUISITE_CHECK = "MODEL_BEHAVIOR.MISSING_PREREQUISITE_CHECK"
    MODEL_BEHAVIOR_UNSAFE_ACTION = "MODEL_BEHAVIOR.UNSAFE_ACTION"
    MODEL_BEHAVIOR_UNSUPPORTED_SUCCESS_CLAIM = "MODEL_BEHAVIOR.UNSUPPORTED_SUCCESS_CLAIM"
    MODEL_BEHAVIOR_INCOMPLETE_TASK_REPORTING = "MODEL_BEHAVIOR.INCOMPLETE_TASK_REPORTING"

    HARNESS_TOOL_SCHEMA_MISMATCH = "HARNESS.TOOL_SCHEMA_MISMATCH"
    HARNESS_CONTEXT_INJECTION_ERROR = "HARNESS.CONTEXT_INJECTION_ERROR"
    HARNESS_STATE_MANAGEMENT_ERROR = "HARNESS.STATE_MANAGEMENT_ERROR"
    HARNESS_TOOL_ORCHESTRATION_ERROR = "HARNESS.TOOL_ORCHESTRATION_ERROR"

    ENVIRONMENT_TOOL_UNAVAILABLE = "ENVIRONMENT.TOOL_UNAVAILABLE"
    ENVIRONMENT_NETWORK_FAILURE = "ENVIRONMENT.NETWORK_FAILURE"
    ENVIRONMENT_PERMISSION_DENIED = "ENVIRONMENT.PERMISSION_DENIED"
    ENVIRONMENT_DEPENDENCY_FAILURE = "ENVIRONMENT.DEPENDENCY_FAILURE"

    DATA_INCOMPLETE_TRACE = "DATA.INCOMPLETE_TRACE"
    DATA_INVALID_CUT = "DATA.INVALID_CUT"
    DATA_MISSING_EVIDENCE = "DATA.MISSING_EVIDENCE"
    DATA_CONTEXT_CORRUPTION = "DATA.CONTEXT_CORRUPTION"

    EVALUATOR_RUBRIC_AMBIGUITY = "EVALUATOR.RUBRIC_AMBIGUITY"
    EVALUATOR_GRADER_DISAGREEMENT = "EVALUATOR.GRADER_DISAGREEMENT"
    EVALUATOR_GRADER_EXECUTION_ERROR = "EVALUATOR.GRADER_EXECUTION_ERROR"
    EVALUATOR_INVALID_TEST_CASE = "EVALUATOR.INVALID_TEST_CASE"

    UNKNOWN_INSUFFICIENT_EVIDENCE = "UNKNOWN.INSUFFICIENT_EVIDENCE"

    @property
    def root(self) -> str:
        return self.value.split(".")[0]

    @property
    def leaf(self) -> str:
        return self.value.split(".")[1]


class EvidenceStrength(str, Enum):
    OBSERVED_FACT = "OBSERVED_FACT"
    SUPPORTED_INFERENCE = "SUPPORTED_INFERENCE"
    UNVERIFIED_HYPOTHESIS = "UNVERIFIED_HYPOTHESIS"
    UNKNOWN = "UNKNOWN"


class DiagnosticEvidence(BaseModel):
    evidence_id: str
    statement: str
    strength: EvidenceStrength
    event_ids: list[str] = Field(default_factory=list)
    source: str = "trace"  # trace | grader | runner | metadata


class RemediationAction(BaseModel):
    target_module: str
    action: str
    rationale: str = ""


class ReviewStatus(str, Enum):
    PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW"
    UNDER_REVIEW = "UNDER_REVIEW"
    REVIEWED = "REVIEWED"


class FailureDiagnosis(BaseModel):
    diagnosis_id: str
    run_id: str
    instance_id: str
    model_id: str
    behavior_id: str
    failed: bool
    primary_category: FailureCategory
    contributing_factors: list[FailureCategory] = Field(default_factory=list)
    evidence: list[DiagnosticEvidence] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    root_cause_confirmable: bool
    root_cause_note: str = ""
    remediation: list[RemediationAction] = Field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.PENDING_HUMAN_REVIEW
    metadata: dict[str, Any] = Field(default_factory=dict)
