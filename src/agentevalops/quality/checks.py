"""Data quality checks.

Each check returns a list of :class:`QualityIssue`. Issues are aggregated into a
per-trace status (VALID / INVALID / PARTIAL / QUARANTINED) by the report module.
Abnormal data is never silently skipped nor are missing events fabricated.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from agentevalops.redaction import Redactor
from agentevalops.schemas.trace import Trace, TraceEvent, TraceEventType

CHECK_VERSION = "1.0"


class IssueSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class QualityIssue(BaseModel):
    code: str
    severity: IssueSeverity
    trace_id: str | None = None
    event_id: str | None = None
    field: str | None = None
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


def check_required_fields(trace: Trace) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    if not trace.trace_id:
        issues.append(
            QualityIssue(code="MISSING_TRACE_ID", severity=IssueSeverity.CRITICAL, field="trace_id", message="trace_id is empty")
        )
    if not trace.source_system:
        issues.append(
            QualityIssue(code="MISSING_SOURCE_SYSTEM", severity=IssueSeverity.ERROR, trace_id=trace.trace_id, field="source_system", message="source_system is empty")
        )
    if not trace.dataset_source:
        issues.append(
            QualityIssue(code="MISSING_DATASET_SOURCE", severity=IssueSeverity.ERROR, trace_id=trace.trace_id, field="dataset_source", message="dataset_source is empty")
        )
    if not trace.events:
        issues.append(
            QualityIssue(code="EMPTY_TRACE", severity=IssueSeverity.CRITICAL, trace_id=trace.trace_id, message="trace has no events")
        )
    for e in trace.events:
        if not e.event_id:
            issues.append(
                QualityIssue(code="MISSING_EVENT_ID", severity=IssueSeverity.ERROR, trace_id=trace.trace_id, message="event missing event_id")
            )
        if e.event_type is None:
            issues.append(
                QualityIssue(code="MISSING_EVENT_TYPE", severity=IssueSeverity.ERROR, trace_id=trace.trace_id, event_id=e.event_id or None, message="event missing event_type")
            )
    return issues


def check_duplicates(trace: Trace) -> list[QualityIssue]:
    seen: set[str] = set()
    issues: list[QualityIssue] = []
    for e in trace.events:
        if e.event_id in seen:
            issues.append(
                QualityIssue(code="DUPLICATE_EVENT_ID", severity=IssueSeverity.ERROR, trace_id=trace.trace_id, event_id=e.event_id, message=f"duplicate event_id {e.event_id}")
            )
        seen.add(e.event_id)
    return issues


def check_event_ordering(trace: Trace) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    last_ts: Any = None
    for e in trace.events:
        if e.timestamp is not None:
            if last_ts is not None and e.timestamp < last_ts:
                issues.append(
                    QualityIssue(code="EVENT_ORDERING", severity=IssueSeverity.WARNING, trace_id=trace.trace_id, event_id=e.event_id, message="event timestamps are not monotonically increasing")
                )
            last_ts = e.timestamp
    return issues


def check_tool_matching(trace: Trace) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    calls: dict[str, TraceEvent] = {}
    results: dict[str, list[TraceEvent]] = {}
    for e in trace.events:
        if e.event_type == TraceEventType.TOOL_CALL and e.tool_call_id:
            calls[e.tool_call_id] = e
        elif e.event_type == TraceEventType.TOOL_RESULT and e.tool_call_id:
            results.setdefault(e.tool_call_id, []).append(e)

    for call_id, call in calls.items():
        if call_id not in results:
            issues.append(
                QualityIssue(code="MISSING_TOOL_RESULT", severity=IssueSeverity.WARNING, trace_id=trace.trace_id, event_id=call.event_id, message=f"tool call {call_id} has no result event")
            )
    for result_id, result_events in results.items():
        if result_id not in calls:
            for r in result_events:
                issues.append(
                    QualityIssue(code="ORPHAN_TOOL_RESULT", severity=IssueSeverity.WARNING, trace_id=trace.trace_id, event_id=r.event_id, message=f"tool result {result_id} has no preceding call")
                )
    return issues


def check_context_completeness(trace: Trace) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    compressed = trace.metadata.get("context_compressed") or trace.metadata.get("compressed")
    if compressed:
        issues.append(
            QualityIssue(code="CONTEXT_COMPRESSION", severity=IssueSeverity.INFO, trace_id=trace.trace_id, message="trace indicates context compression occurred")
        )
    # An assistant event with no content and no following tool call in the same
    # turn is likely a truncated turn.
    events = trace.events
    for i, e in enumerate(events):
        if e.event_type == TraceEventType.ASSISTANT and not e.content:
            has_following_call = any(
                n.turn_id == e.turn_id and n.event_type == TraceEventType.TOOL_CALL for n in events[i + 1 :]
            )
            if not has_following_call:
                issues.append(
                    QualityIssue(code="EMPTY_ASSISTANT_TURN", severity=IssueSeverity.WARNING, trace_id=trace.trace_id, event_id=e.event_id, message="assistant event has no content and no tool calls")
                )
    return issues


def check_oversized(trace: Trace, max_events: int = 10000) -> list[QualityIssue]:
    if len(trace.events) > max_events:
        return [
            QualityIssue(code="OVERSIZED_TRACE", severity=IssueSeverity.WARNING, trace_id=trace.trace_id, message=f"trace has {len(trace.events)} events (>{max_events})")
        ]
    return []


def check_provenance(trace: Trace, allowed_schema_versions: set[str] | None = None) -> list[QualityIssue]:
    allowed = allowed_schema_versions or {"1.0"}
    issues: list[QualityIssue] = []
    if trace.schema_version not in allowed:
        issues.append(
            QualityIssue(code="UNSUPPORTED_SCHEMA_VERSION", severity=IssueSeverity.CRITICAL, trace_id=trace.trace_id, field="schema_version", message=f"schema_version {trace.schema_version!r} not supported")
        )
    return issues


def check_secrets(trace: Trace, redactor: Redactor) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    for e in trace.events:
        hits = redactor.scan_event(e)
        for hit in hits:
            issues.append(
                QualityIssue(
                    code="SENSITIVE_DATA",
                    severity=IssueSeverity.CRITICAL,
                    trace_id=trace.trace_id,
                    event_id=hit.event_id,
                    field=hit.field,
                    message=f"possible {hit.rule} detected in {hit.field}",
                )
            )
    return issues


ALL_CHECKS = [
    check_required_fields,
    check_duplicates,
    check_event_ordering,
    check_tool_matching,
    check_context_completeness,
    check_oversized,
    check_provenance,
]


def run_checks(trace: Trace, redactor: Redactor | None = None) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    for check in ALL_CHECKS:
        issues.extend(check(trace))
    issues.extend(check_secrets(trace, redactor or Redactor()))
    return issues
