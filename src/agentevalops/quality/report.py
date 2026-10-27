"""Data quality report generation and trace status classification."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from agentevalops.quality.checks import CHECK_VERSION, IssueSeverity, QualityIssue, run_checks
from agentevalops.redaction import Redactor
from agentevalops.schemas.trace import Trace


class TraceQualityStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    PARTIAL = "PARTIAL"
    QUARANTINED = "QUARANTINED"


class TraceQuality(BaseModel):
    trace_id: str
    status: TraceQualityStatus
    issues: list[QualityIssue] = Field(default_factory=list)


class DataQualityReport(BaseModel):
    check_version: str = CHECK_VERSION
    checked_at: datetime | None = None
    total: int = 0
    valid: int = 0
    invalid: int = 0
    partial: int = 0
    quarantined: int = 0
    per_trace: list[TraceQuality] = Field(default_factory=list)
    issues: list[QualityIssue] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.invalid == 0 and self.quarantined == 0


def _classify(issues: list[QualityIssue]) -> TraceQualityStatus:
    # Security/provenance problems are quarantined; structural defects are
    # invalid; warnings are partial.
    for i in issues:
        if i.code in ("SENSITIVE_DATA", "UNSUPPORTED_SCHEMA_VERSION"):
            return TraceQualityStatus.QUARANTINED
    has_critical = any(i.severity == IssueSeverity.CRITICAL for i in issues)
    has_error = any(i.severity == IssueSeverity.ERROR for i in issues)
    has_warning = any(i.severity == IssueSeverity.WARNING for i in issues)
    if has_critical or has_error:
        return TraceQualityStatus.INVALID
    if has_warning:
        return TraceQualityStatus.PARTIAL
    return TraceQualityStatus.VALID


def build_quality_report(traces: list[Trace], redactor: Redactor | None = None) -> DataQualityReport:
    redactor = redactor or Redactor()
    report = DataQualityReport(checked_at=datetime.now(timezone.utc), total=len(traces))
    for trace in traces:
        issues = run_checks(trace, redactor)
        status = _classify(issues)
        report.per_trace.append(TraceQuality(trace_id=trace.trace_id, status=status, issues=issues))
        report.issues.extend(issues)
        if status == TraceQualityStatus.VALID:
            report.valid += 1
        elif status == TraceQualityStatus.INVALID:
            report.invalid += 1
        elif status == TraceQualityStatus.PARTIAL:
            report.partial += 1
        else:
            report.quarantined += 1
    return report
