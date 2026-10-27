"""SQLAlchemy ORM models.

Large, nested payloads (responses, config snapshots, evidence) are stored as
JSON columns; original raw traces and large model outputs remain in artifact
files, not stuffed into a single database JSON field.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from agentevalops.persistence.db import Base


class EvalRunRow(Base):
    __tablename__ = "evaluation_runs"

    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    benchmark_id: Mapped[str] = mapped_column(String(128), index=True)
    dataset_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    models: Mapped[list[str]] = mapped_column(JSON, default=list)
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)


class EvalTrialRow(Base):
    __tablename__ = "evaluation_trials"

    trial_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(128), ForeignKey("evaluation_runs.run_id"), index=True)
    instance_id: Mapped[str] = mapped_column(String(256), index=True)
    model_id: Mapped[str] = mapped_column(String(128), index=True)
    behavior_id: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32))
    response: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    usage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)


class GradingResultRow(Base):
    __tablename__ = "grading_results"

    grading_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trial_id: Mapped[str] = mapped_column(String(256), index=True)
    run_id: Mapped[str] = mapped_column(String(128), index=True)
    instance_id: Mapped[str] = mapped_column(String(256), index=True)
    model_id: Mapped[str] = mapped_column(String(128), index=True)
    behavior_id: Mapped[str] = mapped_column(String(128), index=True)
    deterministic_hits: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    rubric_verdict: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    hybrid: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    grader_version: Mapped[str] = mapped_column(String(32))


class FailureDiagnosisRow(Base):
    __tablename__ = "failure_diagnoses"

    diagnosis_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(128), index=True)
    instance_id: Mapped[str] = mapped_column(String(256), index=True)
    model_id: Mapped[str] = mapped_column(String(128), index=True)
    behavior_id: Mapped[str] = mapped_column(String(128), index=True)
    failed: Mapped[bool] = mapped_column(Boolean)
    primary_category: Mapped[str] = mapped_column(String(128), index=True)
    contributing_factors: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    hypotheses: Mapped[list[str]] = mapped_column(JSON, default=list)
    root_cause_confirmable: Mapped[bool] = mapped_column(Boolean)
    root_cause_note: Mapped[str] = mapped_column(Text, default="")
    remediation: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    review_status: Mapped[str] = mapped_column(String(64))
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)


class HumanReviewRow(Base):
    __tablename__ = "human_reviews"

    review_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(128), index=True)
    instance_id: Mapped[str] = mapped_column(String(256))
    model_id: Mapped[str] = mapped_column(String(128))
    reviewer: Mapped[str] = mapped_column(String(128))
    decision: Mapped[str] = mapped_column(String(32))
    aspects: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class FeedbackRecordRow(Base):
    __tablename__ = "feedback_records"

    record_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(128), index=True)
    instance_id: Mapped[str] = mapped_column(String(256))
    model_id: Mapped[str] = mapped_column(String(128))
    behavior_id: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(64), index=True)
    review_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    has_wrong_response: Mapped[bool] = mapped_column(Boolean, default=False)
    has_verified_correct_response: Mapped[bool] = mapped_column(Boolean, default=False)
    has_verified_preference_pair: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
