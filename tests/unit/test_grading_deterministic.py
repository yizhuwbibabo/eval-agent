"""Deterministic grading tests."""

from __future__ import annotations

from agentevalops.evaluation.prompting import build_prompt
from agentevalops.evaluation.providers.mock import compliant, error_prone, wrong_tool
from agentevalops.grading.deterministic import evaluate_deterministic, hard_violations


def _hits(instance, turn):
    return evaluate_deterministic(instance, turn)


def test_compliant_passes_all(instances) -> None:
    for inst in instances.values():
        turn = compliant(build_prompt(inst))
        assert not hard_violations(_hits(inst, turn))


def test_error_prone_repeats_failing_call(instances) -> None:
    inst = instances["syn_error_correction_wrong::e4"]
    turn = error_prone(build_prompt(inst))
    hits = _hits(inst, turn)
    assert not hard_violations(hits)  # soft violation, not a hard constraint
    matched = {h.rule_id for h in hits if h.matched}
    assert "no_repeat_of_failing_operation" in matched
    assert "error_correction_applied" in matched


def test_wrong_tool_is_hard_violation(instances) -> None:
    inst = instances["syn_error_correction_wrong::e4"]
    turn = wrong_tool(build_prompt(inst))
    hits = _hits(inst, turn)
    assert any(h.rule_id == "tool_name_validity" and h.matched for h in hits)
    assert hard_violations(hits)


def test_unsafe_action_is_hard_violation(instances) -> None:
    inst = instances["syn_unsafe_wrong::e3"]
    turn = error_prone(build_prompt(inst))
    hits = _hits(inst, turn)
    assert any(h.rule_id == "no_unauthorized_destructive_action" and h.matched for h in hits)
    assert hard_violations(hits)


def test_tool_argument_required_fields(instances) -> None:
    from agentevalops.schemas.evaluation import AssistantTurn, ToolCall

    inst = instances["syn_log_inspection_wrong::e4"]
    turn = AssistantTurn(tool_calls=[ToolCall(call_id="c1", tool_name="read_logs", arguments={})])
    hits = _hits(inst, turn)
    assert any(h.rule_id == "tool_argument_required_fields" and h.matched for h in hits)


def test_claim_without_verification(instances) -> None:
    inst = instances["syn_post_edit_wrong::e5"]
    turn = error_prone(build_prompt(inst))
    hits = _hits(inst, turn)
    matched = {h.rule_id for h in hits if h.matched}
    assert "verification_before_claim" in matched
    assert "no_ungrounded_success_claim" in matched
