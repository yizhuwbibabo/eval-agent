"""Tool-error anchor: tool results that returned an error."""

from __future__ import annotations

from typing import Any

from agentevalops.benchmark.anchors.base import Anchor
from agentevalops.benchmark.anchors.matching import event_matches
from agentevalops.benchmark.trace_utils import find_call
from agentevalops.schemas.behavior import BehaviorSpecification
from agentevalops.schemas.benchmark import Candidate
from agentevalops.schemas.trace import Trace, TraceEventType


class ToolErrorAnchor(Anchor):
    name = "tool_error"

    def scan(self, trace: Trace, behavior: BehaviorSpecification) -> list[Candidate]:
        if not self._context_filter_passes(trace, behavior):
            return []
        params = behavior.anchor_definition.params
        candidates: list[Candidate] = []
        for e in trace.events:
            if e.event_type != TraceEventType.TOOL_RESULT:
                continue
            is_error = e.error is not None or (e.status is not None and e.status.value == "error")
            if not is_error and not event_matches(e, {"event_type": "tool_result", "statuses": params.get("statuses") or []}):
                continue
            if not (e.error or (e.status is not None and e.status.value == "error")):
                continue
            call = find_call(trace, e.tool_call_id)
            metadata: dict[str, Any] = {
                "tool_name": call.tool_name if call else e.tool_name,
                "error_event_id": e.event_id,
                "error": e.error,
                "original_arguments": call.tool_arguments if call else None,
                "tool_result": e.tool_result,
            }
            candidates.append(self._candidate(trace, behavior, e.event_id, [e.event_id], metadata))
        return candidates
