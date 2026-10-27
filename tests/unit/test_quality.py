"""Data quality check tests."""

from __future__ import annotations

from agentevalops.datagen import (
    empty_trace,
    incomplete_missing_result,
    orphan_tool_result,
    secret_trace,
)
from agentevalops.quality.report import TraceQualityStatus, build_quality_report


def test_incomplete_trace_is_partial() -> None:
    report = build_quality_report([incomplete_missing_result()])
    assert report.per_trace[0].status == TraceQualityStatus.PARTIAL
    assert any(i.code == "MISSING_TOOL_RESULT" for i in report.issues)


def test_orphan_result_is_partial() -> None:
    report = build_quality_report([orphan_tool_result()])
    assert report.per_trace[0].status == TraceQualityStatus.PARTIAL
    assert any(i.code == "ORPHAN_TOOL_RESULT" for i in report.issues)


def test_empty_trace_is_invalid() -> None:
    report = build_quality_report([empty_trace()])
    assert report.per_trace[0].status == TraceQualityStatus.INVALID
    assert any(i.code == "EMPTY_TRACE" for i in report.issues)


def test_secret_trace_is_quarantined() -> None:
    report = build_quality_report([secret_trace()])
    assert report.per_trace[0].status == TraceQualityStatus.QUARANTINED
    assert any(i.code == "SENSITIVE_DATA" for i in report.issues)


def test_duplicate_event_detected() -> None:
    from agentevalops.schemas.trace import Trace, TraceEvent, TraceEventType

    trace = Trace(
        trace_id="dup",
        source_system="x",
        dataset_source="synthetic",
        events=[
            TraceEvent(event_id="e1", event_type=TraceEventType.USER, content="a"),
            TraceEvent(event_id="e1", event_type=TraceEventType.USER, content="b"),
        ],
    )
    report = build_quality_report([trace])
    assert any(i.code == "DUPLICATE_EVENT_ID" for i in report.issues)
