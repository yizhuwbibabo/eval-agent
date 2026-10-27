"""Typed exceptions and stable error codes for AgentEvalOps.

Every raised error carries a stable ``code`` so that downstream components
(and reports) can distinguish model behavior failures from infrastructure,
harness, evaluator and data failures without inspecting message strings.
"""

from __future__ import annotations

from typing import Any


class AgentEvalOpsError(Exception):
    """Base class for all AgentEvalOps errors."""

    code = "AGENTEVALOPS_ERROR"

    def __init__(self, message: str, *, code: str | None = None, **context: Any) -> None:
        self.message = message
        self.code = code or self.__class__.code
        self.context: dict[str, Any] = context
        super().__init__(message)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"[{self.code}] {self.message}"


# --- Data / schema ---
class SchemaValidationError(AgentEvalOpsError):
    code = "SCHEMA_VALIDATION_ERROR"


class IngestionError(AgentEvalOpsError):
    code = "INGESTION_ERROR"


class DataQualityError(AgentEvalOpsError):
    code = "DATA_QUALITY_ERROR"


class RedactionError(AgentEvalOpsError):
    code = "REDACTION_ERROR"


# --- Benchmark construction ---
class AnchorError(AgentEvalOpsError):
    code = "ANCHOR_ERROR"


class ConfirmationError(AgentEvalOpsError):
    code = "CONFIRMATION_ERROR"


class CutError(AgentEvalOpsError):
    code = "CUT_ERROR"


class BenchmarkBuildError(AgentEvalOpsError):
    code = "BENCHMARK_BUILD_ERROR"


# --- Evaluation ---
class EvaluationError(AgentEvalOpsError):
    code = "EVALUATION_ERROR"


class ProviderError(AgentEvalOpsError):
    code = "PROVIDER_ERROR"


class ProviderTimeoutError(ProviderError):
    code = "TIMEOUT"


class RateLimitError(ProviderError):
    code = "RATE_LIMIT"


class ProviderUnavailableError(ProviderError):
    code = "PROVIDER_UNAVAILABLE"


class UnsupportedModelCapability(ProviderError):
    code = "UNSUPPORTED_MODEL_CAPABILITY"


# --- Grading ---
class GraderError(AgentEvalOpsError):
    code = "GRADER_ERROR"


class GraderExecutionError(GraderError):
    code = "GRADER_EXECUTION_ERROR"


# --- Diagnosis / reporting / persistence ---
class DiagnosisError(AgentEvalOpsError):
    code = "DIAGNOSIS_ERROR"


class ReportingError(AgentEvalOpsError):
    code = "REPORTING_ERROR"


class PersistenceError(AgentEvalOpsError):
    code = "PERSISTENCE_ERROR"


# Mapping from error code to whether it is an *infrastructure* (retryable) error
# vs a model-behavior / data error. Used by the runner's retry policy.
RETRYABLE_CODES = frozenset(
    {
        "TIMEOUT",
        "RATE_LIMIT",
        "PROVIDER_UNAVAILABLE",
        "PROVIDER_ERROR",
    }
)
