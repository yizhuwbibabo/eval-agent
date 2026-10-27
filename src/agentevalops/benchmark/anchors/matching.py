"""Shared criteria-matching helpers for anchors."""

from __future__ import annotations

from typing import Any

from agentevalops.schemas.trace import TraceEvent, TraceEventType


def event_matches(event: TraceEvent, criteria: dict[str, Any]) -> bool:
    event_type = criteria.get("event_type")
    if event_type:
        try:
            expected = TraceEventType(event_type)
        except ValueError:
            return False
        if event.event_type != expected:
            return False
    tool_names = criteria.get("tool_names")
    if tool_names and (event.tool_name not in tool_names):
        return False
    statuses = criteria.get("statuses")
    if statuses:
        if event.status is None or event.status.value not in statuses:
            return False
    if criteria.get("require_content") and not event.content:
        return False
    if criteria.get("require_error") and not (event.error or _result_is_error(event)):
        return False
    return True


def _result_is_error(event: TraceEvent) -> bool:
    result = event.tool_result
    if isinstance(result, dict):
        return bool(result.get("error")) or result.get("ok") is False
    return False
