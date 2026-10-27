"""Error-instruction anchor: tool errors that explicitly state a correction.

The anchor looks for tool results whose structured payload carries an explicit
correction instruction (e.g. ``suggested_fix``), rather than any keyword in a
free-text error string.
"""

from __future__ import annotations

from typing import Any

from agentevalops.benchmark.anchors.base import Anchor
from agentevalops.benchmark.trace_utils import find_call
from agentevalops.schemas.behavior import BehaviorSpecification
from agentevalops.schemas.benchmark import Candidate
from agentevalops.schemas.trace import Trace, TraceEventType


class ErrorInstructionAnchor(Anchor):
    name = "error_instruction"

    def scan(self, trace: Trace, behavior: BehaviorSpecification) -> list[Candidate]:
        if not self._context_filter_passes(trace, behavior):
            return []
        params = behavior.anchor_definition.params
        instruction_keys = params.get("instruction_keys") or [
            "suggested_fix",
            "correction",
            "suggested_correction",
        ]
        candidates: list[Candidate] = []
        for e in trace.events:
            if e.event_type != TraceEventType.TOOL_RESULT:
                continue
            if not isinstance(e.tool_result, dict):
                continue
            correction: Any = None
            matched_key: str | None = None
            for key in instruction_keys:
                if key in e.tool_result:
                    correction = e.tool_result[key]
                    matched_key = key
                    break
            if correction is None:
                continue
            call = find_call(trace, e.tool_call_id)
            metadata: dict[str, Any] = {
                "tool_name": call.tool_name if call else e.tool_name,
                "error_event_id": e.event_id,
                "error": e.tool_result.get("error") or e.error,
                "original_arguments": call.tool_arguments if call else None,
                "suggested_correction": correction,
                "instruction_key": matched_key,
            }
            candidates.append(self._candidate(trace, behavior, e.event_id, [e.event_id], metadata))
        return candidates
