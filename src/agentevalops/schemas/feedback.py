"""Human review and training-feedback schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ReviewDecision(str, Enum):
    CONFIRM = "confirm"
    REJECT = "reject"
    FLAG = "flag"


class HumanReview(BaseModel):
    review_id: str
    run_id: str
    instance_id: str
    model_id: str
    reviewer: str
    decision: ReviewDecision
    # Which aspect the reviewer judged.
    aspects: list[str] = Field(
        default_factory=lambda: ["sample_validity", "behavior_occurrence", "grader_correct"]
    )
    notes: str = ""
    reviewed_at: datetime | None = None
    version: int = 1


class FeedbackStatus(str, Enum):
    NEW = "NEW"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    HUMAN_CONFIRMED = "HUMAN_CONFIRMED"
    REJECTED = "REJECTED"
    APPROVED_FOR_TRAINING = "APPROVED_FOR_TRAINING"


class FeedbackRecord(BaseModel):
    record_id: str
    run_id: str
    instance_id: str
    model_id: str
    behavior_id: str
    status: FeedbackStatus = FeedbackStatus.NEW
    review_id: str | None = None
    # Training-pair categories, kept distinct so that an unverified grader
    # output is never silently promoted to a training label.
    has_wrong_response: bool = False
    has_verified_correct_response: bool = False
    has_verified_preference_pair: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
