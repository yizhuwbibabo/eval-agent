"""Agent behavior evaluation metrics.

Pass rates are reported separately by model, behavior, benchmark, version and
run. Macro and micro pass rates are never conflated: macro averages per-behavior
rates (weighting each behavior equally), micro pools all trials.
"""

from __future__ import annotations

from typing import Any

from agentevalops.schemas.evaluation import TrialResult, TrialStatus
from agentevalops.schemas.grading import GradingResult


def _definite(gradings: list[GradingResult]) -> list[GradingResult]:
    return [g for g in gradings if g.hybrid is not None and g.hybrid.passed is not None]


def _pass_rate(gradings: list[GradingResult]) -> float | None:
    definite = _definite(gradings)
    if not definite:
        return None
    return sum(1 for g in definite if g.hybrid and g.hybrid.passed) / len(definite)


def evaluation_metrics(
    trials: list[TrialResult],
    gradings: list[GradingResult],
    behaviors: list[str] | None = None,
) -> dict[str, Any]:
    grading_by_trial = {g.trial_id: g for g in gradings}
    completed = [t for t in trials if t.status == TrialStatus.COMPLETED]
    failed = [t for t in trials if t.status == TrialStatus.FAILED]
    unsupported = [t for t in trials if t.status == TrialStatus.UNSUPPORTED]

    models = sorted({t.model_id for t in trials})
    behavior_set = behaviors or sorted({t.behavior_id for t in trials})

    by_model: dict[str, Any] = {}
    for model in models:
        gs = [grading_by_trial[t.trial_id] for t in completed if t.model_id == model and t.trial_id in grading_by_trial]
        by_model[model] = {
            "pass_rate": _pass_rate(gs),
            "definite_trials": len(_definite(gs)),
            "completed": len([t for t in completed if t.model_id == model]),
            "failed": len([t for t in failed if t.model_id == model]),
            "unsupported": len([t for t in unsupported if t.model_id == model]),
        }

    by_behavior: dict[str, Any] = {}
    for behavior in behavior_set:
        gs = [grading_by_trial[t.trial_id] for t in completed if t.behavior_id == behavior and t.trial_id in grading_by_trial]
        pr = _pass_rate(gs)
        by_behavior[behavior] = {
            "pass_rate": pr,
            "failure_rate": (1 - pr) if pr is not None else None,
            "definite_trials": len(_definite(gs)),
        }

    per_behavior_pass = [by_behavior[b]["pass_rate"] for b in by_behavior if by_behavior[b]["pass_rate"] is not None]
    macro_pass_rate = (sum(per_behavior_pass) / len(per_behavior_pass)) if per_behavior_pass else None

    all_gs = [grading_by_trial[t.trial_id] for t in completed if t.trial_id in grading_by_trial]
    micro_pass_rate = _pass_rate(all_gs)

    # Tool-call validity across all tool calls in graded trials.
    total_calls = 0
    valid_calls = 0
    for g in gradings:
        for hit in g.deterministic_hits:
            if hit.rule_id == "tool_name_validity":
                total_calls += 1
                if not hit.matched:
                    valid_calls += 1

    safety = by_behavior.get("unsafe_action_without_confirmation", {})
    error_recovery = by_behavior.get("error_guided_correction", {})
    claim = by_behavior.get("post_edit_verification", {})

    return {
        "total_trials": len(trials),
        "completed": len(completed),
        "failed_infra": len(failed),
        "unsupported": len(unsupported),
        "micro_pass_rate": micro_pass_rate,
        "macro_pass_rate": macro_pass_rate,
        "failure_rate_by_behavior": {b: by_behavior[b]["failure_rate"] for b in by_behavior},
        "behavior_pass_rate": {b: by_behavior[b]["pass_rate"] for b in by_behavior},
        "tool_call_validity": (valid_calls / total_calls) if total_calls else None,
        "error_recovery_pass_rate": error_recovery.get("pass_rate"),
        "safety_violation_rate": (1 - safety["pass_rate"]) if safety.get("pass_rate") is not None else None,
        "claim_grounding_pass_rate": claim.get("pass_rate"),
        "by_model": by_model,
        "by_behavior": by_behavior,
    }
