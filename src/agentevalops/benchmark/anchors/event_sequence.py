"""Event-sequence anchor.

Finds a ``target`` event that follows a ``before`` event while a required
``missing_between`` event type does not occur in between. This is used for
post-edit verification (edit -> claim without verification) and unsafe-action
(no confirmation before a destructive action).
"""

from __future__ import annotations

from typing import Any

from agentevalops.benchmark.anchors.base import Anchor
from agentevalops.benchmark.anchors.matching import event_matches
from agentevalops.benchmark.trace_utils import is_terminal_assistant
from agentevalops.schemas.behavior import BehaviorSpecification
from agentevalops.schemas.benchmark import Candidate
from agentevalops.schemas.trace import Trace, TraceEventType


class EventSequenceAnchor(Anchor):
    name = "event_sequence"

    def scan(self, trace: Trace, behavior: BehaviorSpecification) -> list[Candidate]:
        if not self._context_filter_passes(trace, behavior):
            return []
        params = behavior.anchor_definition.params
        before = params.get("before") or {}
        target = params.get("target") or {}
        missing_between = params.get("missing_between") or {}

        candidates: list[Candidate] = []
        events = trace.events
        for i, e in enumerate(events):
            if not event_matches(e, target):
                continue
            if target.get("terminal") and not is_terminal_assistant(trace, i):
                continue

            before_idx = self._find_before(events, i, before)
            if before_idx is None:
                continue

            if self._has_missing_between(events, before_idx, i, missing_between):
                continue

            metadata: dict[str, Any] = {
                "target_event_id": e.event_id,
                "before_event_id": events[before_idx].event_id if before_idx >= 0 else None,
            }
            extra = {
                k: v
                for k, v in params.items()
                if k not in ("before", "target", "missing_between", "context_filter")
            }
            metadata.update(extra)
            evidence = [events[before_idx].event_id, e.event_id] if before_idx >= 0 else [e.event_id]
            candidates.append(
                self._candidate(trace, behavior, e.event_id, [ev for ev in evidence if ev], metadata)
            )
        return candidates

    def _find_before(self, events: list, target_idx: int, before: dict[str, Any]) -> int | None:
        if not before:
            # Default: last user message before target, else start of trace.
            for i in range(target_idx - 1, -1, -1):
                if events[i].event_type == TraceEventType.USER:
                    return i
            return 0
        for i in range(target_idx - 1, -1, -1):
            if event_matches(events[i], before):
                return i
        return None

    def _has_missing_between(
        self, events: list, before_idx: int, target_idx: int, missing_between: dict[str, Any]
    ) -> bool:
        if not missing_between:
            return False
        for i in range(before_idx + 1, target_idx):
            if event_matches(events[i], missing_between):
                return True
        return False
