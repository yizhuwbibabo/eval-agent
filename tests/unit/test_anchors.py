"""Anchor recall tests."""

from __future__ import annotations

from agentevalops.benchmark.anchors.registry import get_anchor
from agentevalops.datagen import (
    error_guided_correction_clean,
    error_guided_correction_right,
    error_guided_correction_wrong,
    failure_log_inspection_right,
    failure_log_inspection_wrong,
    post_edit_verification_right,
    post_edit_verification_wrong,
    unsafe_action_right,
    unsafe_action_wrong,
)


def _scan(behavior_id, trace, registry) -> list:
    behavior = registry.get(behavior_id)
    anchor = get_anchor(behavior.anchor_definition.anchor_type)
    return anchor.scan(trace, behavior)


def test_error_instruction_anchor_recalls_wrong(registry) -> None:
    cands = _scan("error_guided_correction", error_guided_correction_wrong(), registry)
    assert len(cands) == 1
    assert cands[0].cut_event_id == "e4"
    assert "suggested_correction" in cands[0].metadata


def test_error_instruction_anchor_skips_clean(registry) -> None:
    assert _scan("error_guided_correction", error_guided_correction_clean(), registry) == []


def test_status_check_anchor_recalls_failure(registry) -> None:
    cands = _scan("failure_log_inspection", failure_log_inspection_wrong(), registry)
    assert len(cands) == 1
    assert cands[0].metadata["failure_event_id"] == "e4"


def test_event_sequence_anchor_post_edit(registry) -> None:
    wrong = _scan("post_edit_verification", post_edit_verification_wrong(), registry)
    right = _scan("post_edit_verification", post_edit_verification_right(), registry)
    assert len(wrong) == 1
    assert len(right) == 0  # verification present -> no candidate


def test_event_sequence_anchor_unsafe(registry) -> None:
    wrong = _scan("unsafe_action_without_confirmation", unsafe_action_wrong(), registry)
    right = _scan("unsafe_action_without_confirmation", unsafe_action_right(), registry)
    assert len(wrong) == 1
    assert len(right) == 0  # confirmation present -> no candidate


def test_anchor_does_not_false_positive_on_right_behavior(registry) -> None:
    # The "right" traces still contain the error, but the source applied the
    # correction / inspected logs, so the confirmation (not the anchor) rejects.
    cands = _scan("error_guided_correction", error_guided_correction_right(), registry)
    assert len(cands) == 1  # recall still fires on the error event
    cands2 = _scan("failure_log_inspection", failure_log_inspection_right(), registry)
    assert len(cands2) == 1
