"""Argument-check anchor: tool calls whose arguments match constraints."""

from __future__ import annotations

from typing import Any

from agentevalops.benchmark.anchors.base import Anchor
from agentevalops.benchmark.anchors.matching import event_matches
from agentevalops.schemas.behavior import BehaviorSpecification
from agentevalops.schemas.benchmark import Candidate
from agentevalops.schemas.trace import Trace, TraceEventType


class ArgumentCheckAnchor(Anchor):
    name = "argument_check"

    def scan(self, trace: Trace, behavior: BehaviorSpecification) -> list[Candidate]:
        if not self._context_filter_passes(trace, behavior):
            return []
        params = behavior.anchor_definition.params
        forbidden_args = params.get("forbidden_args") or {}
        required_args = params.get("required_args") or []
        candidates: list[Candidate] = []
        for e in trace.events:
            if e.event_type != TraceEventType.TOOL_CALL:
                continue
            if not event_matches(e, params):
                continue
            args = e.tool_arguments or {}
            hit = False
            for key, forbidden_values in forbidden_args.items():
                if key in args and (not forbidden_values or args[key] in forbidden_values):
                    hit = True
            for key in required_args:
                if key not in args:
                    hit = True
            if not hit:
                continue
            metadata: dict[str, Any] = {
                "action_event_id": e.event_id,
                "tool_name": e.tool_name,
                "tool_arguments": args,
            }
            candidates.append(self._candidate(trace, behavior, e.event_id, [e.event_id], metadata))
        return candidates
