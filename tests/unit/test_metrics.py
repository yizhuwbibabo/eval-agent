"""Metrics tests."""

from __future__ import annotations

from agentevalops.metrics.bootstrap import bootstrap_ci, paired_pass_rate_ci
from agentevalops.metrics.engineering import engineering_metrics
from agentevalops.metrics.evaluation import evaluation_metrics
from agentevalops.schemas.evaluation import TrialResult, TrialStatus, Usage
from agentevalops.schemas.grading import GradeStatus, GradingResult, HybridVerdict


def _trial(tid, model, behavior, status=TrialStatus.COMPLETED, latency=10.0):
    return TrialResult(
        trial_id=tid,
        run_id="r",
        instance_id=f"inst_{tid}",
        model_id=model,
        behavior_id=behavior,
        status=status,
        latency_ms=latency,
        usage=Usage(input_tokens=1, output_tokens=1, total_tokens=2),
    )


def _grading(tid, passed: bool | None, status=GradeStatus.GRADED):
    return GradingResult(
        trial_id=tid,
        run_id="r",
        instance_id=f"inst_{tid}",
        model_id="m",
        behavior_id="b",
        hybrid=HybridVerdict(final_score=5.0 if passed else 0.0, passed=passed, strategy="hybrid", status=status),
    )


def test_evaluation_metrics_micro_macro() -> None:
    trials = [
        _trial("a1", "a", "b1"),
        _trial("a2", "a", "b2"),
        _trial("b1", "b", "b1"),
        _trial("b2", "b", "b2"),
    ]
    gradings = [
        _grading("a1", True),
        _grading("a2", True),
        _grading("b1", False),
        _grading("b2", False),
    ]
    m = evaluation_metrics(trials, gradings)
    assert m["micro_pass_rate"] == 0.5
    assert m["macro_pass_rate"] == 0.5
    assert m["by_model"]["a"]["pass_rate"] == 1.0
    assert m["by_model"]["b"]["pass_rate"] == 0.0


def test_evaluation_metrics_excludes_undetermined() -> None:
    trials = [_trial("a1", "a", "b1"), _trial("a2", "a", "b1")]
    gradings = [_grading("a1", True), _grading("a2", None, GradeStatus.INSUFFICIENT_EVIDENCE)]
    m = evaluation_metrics(trials, gradings)
    assert m["micro_pass_rate"] == 1.0  # only definite trials counted


def test_engineering_metrics_latency() -> None:
    trials = [_trial("a1", "a", "b1", latency=10.0), _trial("a2", "a", "b1", latency=20.0)]
    m = engineering_metrics(trials, [])
    assert m["latency_mean_ms"] == 15.0
    assert m["latency_p50_ms"] == 15.0
    assert m["latency_p95_ms"] == 19.5  # linear-interpolated p95 of [10, 20]


def test_engineering_metrics_counts_infra_separately() -> None:
    trials = [
        _trial("a1", "a", "b1"),
        _trial("a2", "a", "b1", status=TrialStatus.FAILED),
    ]
    t = trials[1]
    t.error_code = "TIMEOUT"
    m = engineering_metrics(trials, [])
    assert m["api_error_rate"] == 0.5
    assert m["timeout_rate"] == 0.5


def test_bootstrap_ci() -> None:
    ci = bootstrap_ci([1.0, 0.0, 1.0, 0.0], n_bootstrap=100, seed=1)
    assert ci["mean"] == 0.5
    assert ci["ci_low"] <= 0.5 <= ci["ci_high"]


def test_paired_pass_rate_ci() -> None:
    ci = paired_pass_rate_ci([(True, False), (True, False), (False, True)], n_bootstrap=100, seed=1)
    assert "diff_mean" in ci
