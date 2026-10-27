"""Decision-point cutting and leak-check tests."""

from __future__ import annotations

import pytest

from agentevalops.benchmark.anchors.registry import get_anchor
from agentevalops.benchmark.cutting.cutter import cut
from agentevalops.benchmark.cutting.leak_check import assert_no_leak, check_leak
from agentevalops.datagen import (
    error_guided_correction_wrong,
    post_edit_verification_wrong,
    unsafe_action_wrong,
)


def _cut(trace, behavior_id, registry):
    behavior = registry.get(behavior_id)
    anchor = get_anchor(behavior.anchor_definition.anchor_type)
    cand = anchor.scan(trace, behavior)[0]
    return cut(trace, behavior, cand)


def test_failure_cut_keeps_error_drops_continuation(registry) -> None:
    trace = error_guided_correction_wrong()
    result = _cut(trace, "error_guided_correction", registry)
    # Context ends at the error event (e4); the next turn (e5-e7) is dropped.
    ids = [m.event_id for m in result.context]
    assert "e4" in ids
    assert "e5" not in ids and "e6" not in ids
    assert result.target_event_ids  # the source continuation is tracked for audit


def test_action_cut_excludes_action_turn(registry) -> None:
    trace = unsafe_action_wrong()
    result = _cut(trace, "unsafe_action_without_confirmation", registry)
    ids = [m.event_id for m in result.context]
    # The assistant preamble (e2) and the destructive call (e3) are in the
    # action turn and must not leak; only the user message (e1) remains.
    assert "e1" in ids
    assert "e2" not in ids and "e3" not in ids


def test_claim_cut_excludes_claim(registry) -> None:
    trace = post_edit_verification_wrong()
    result = _cut(trace, "post_edit_verification", registry)
    ids = [m.event_id for m in result.context]
    assert "e5" not in ids  # the claim is dropped
    assert "e4" in ids  # the edit result is kept


def test_no_leak_assertion(registry) -> None:
    trace = error_guided_correction_wrong()
    result = _cut(trace, "error_guided_correction", registry)
    target = [e for eid in result.target_event_ids if (e := trace.event_by_id(eid))]
    assert check_leak(result.context, target) == []
    assert_no_leak(result.context, target)


def test_leak_detected_when_context_contains_target(registry) -> None:
    trace = error_guided_correction_wrong()
    result = _cut(trace, "error_guided_correction", registry)
    target = [e for eid in result.target_event_ids if (e := trace.event_by_id(eid))]
    # Simulate a leak by appending a target event to the context.
    from agentevalops.schemas.benchmark import ContextMessage

    leaked = result.context + [ContextMessage(role="assistant", content=target[0].content, event_id=target[0].event_id)]
    assert check_leak(leaked, target)


def test_cut_missing_event_raises(registry) -> None:
    from agentevalops.schemas.benchmark import Candidate

    trace = error_guided_correction_wrong()
    behavior = registry.get("error_guided_correction")
    with pytest.raises(ValueError):
        cut(trace, behavior, Candidate(
            candidate_id="x",
            behavior_id="error_guided_correction",
            source_trace_id=trace.trace_id,
            cut_event_id="does_not_exist",
            anchor_name="x",
            anchor_version="1",
        ))
