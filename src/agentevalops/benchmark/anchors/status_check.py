"""Status-check anchor: events matching a status (e.g. background task failure)."""

from __future__ import annotations

from typing import Any

from agentevalops.benchmark.anchors.base import Anchor
from agentevalops.benchmark.anchors.matching import event_matches
from agentevalops.benchmark.trace_utils import find_call
from agentevalops.schemas.behavior import BehaviorSpecification
from agentevalops.schemas.benchmark import Candidate
from agentevalops.schemas.trace import Trace


class StatusCheckAnchor(Anchor):
    name = "status_check"

    def scan(self, trace: Trace, behavior: BehaviorSpecification) -> list[Candidate]:
        if not self._context_filter_passes(trace, behavior):
            return []
        params = behavior.anchor_definition.params
        candidates: list[Candidate] = []
        for e in trace.events:
            if not event_matches(e, params):
                continue
            call = find_call(trace, e.tool_call_id)
            # Pass through any non-matching params so the cutter/graders can use
            # them (e.g. inspection_tools, modify_tools).
            extra = {
                k: v
                for k, v in params.items()
                if k not in ("event_type", "event_types", "statuses", "tool_names", "context_filter")
            }
            metadata: dict[str, Any] = {
                "failure_event_id": e.event_id,
                "tool_name": call.tool_name if call else e.tool_name,
                "original_arguments": call.tool_arguments if call else None,
                "status": e.status.value if e.status else None,
                "error": e.error,
                "tool_result": e.tool_result,
                **extra,
            }
            candidates.append(self._candidate(trace, behavior, e.event_id, [e.event_id], metadata))
        return candidates
