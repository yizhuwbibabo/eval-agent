"""Evaluation run, trial and model-response schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    call_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


class AssistantTurn(BaseModel):
    """The model's next assistant turn at a decision point.

    Preserves text, one or more tool calls, finish reason and provider metadata
    rather than assuming a text-only response.
    """

    text: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: str | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    usage: Usage = Field(default_factory=Usage)


class RunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TrialStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    UNSUPPORTED = "UNSUPPORTED"


class TrialResult(BaseModel):
    trial_id: str
    run_id: str
    instance_id: str
    model_id: str
    behavior_id: str
    status: TrialStatus
    response: AssistantTurn | None = None
    error: str | None = None
    error_code: str | None = None
    latency_ms: float | None = None
    usage: Usage = Field(default_factory=Usage)
    retries: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvalRun(BaseModel):
    run_id: str
    benchmark_id: str
    dataset_version: str
    status: RunStatus
    models: list[str] = Field(default_factory=list)
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
