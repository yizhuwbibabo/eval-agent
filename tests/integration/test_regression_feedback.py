"""Regression comparison, feedback and leakage tests."""

from __future__ import annotations

from agentevalops.feedback.leakage import check_leakage, grouped_split
from agentevalops.reporting.data import RunArtifacts
from agentevalops.reporting.regression import compare_runs
from agentevalops.schemas.evaluation import EvalRun, RunStatus, TrialResult, TrialStatus
from agentevalops.schemas.grading import GradeStatus, GradingResult, HybridVerdict


def _run(run_id: str, trials: list[dict]) -> RunArtifacts:
    t = [
        TrialResult(
            trial_id=tr["id"],
            run_id=run_id,
            instance_id=tr["inst"],
            model_id=tr["model"],
            behavior_id="b",
            status=TrialStatus(tr["status"]),
        )
        for tr in trials
    ]
    g = [
        GradingResult(
            trial_id=tr["id"],
            run_id=run_id,
            instance_id=tr["inst"],
            model_id=tr["model"],
            behavior_id="b",
            hybrid=HybridVerdict(final_score=tr.get("score", 5.0), passed=tr.get("passed"), strategy="hybrid", status=GradeStatus.GRADED),
        )
        for tr in trials
        if tr["status"] == "COMPLETED"
    ]
    run = EvalRun(run_id=run_id, benchmark_id="b", dataset_version="v1", status=RunStatus.COMPLETED)
    return RunArtifacts(run=run, trials=t, gradings=g, diagnoses=[])


def test_regression_detects_improved_and_regressed() -> None:
    base = _run(
        "base",
        [
            {"id": "t1", "inst": "i1", "model": "m", "status": "COMPLETED", "passed": False, "score": 0.0},
            {"id": "t2", "inst": "i2", "model": "m", "status": "COMPLETED", "passed": True, "score": 5.0},
        ],
    )
    cand = _run(
        "cand",
        [
            {"id": "t1", "inst": "i1", "model": "m", "status": "COMPLETED", "passed": True, "score": 5.0},
            {"id": "t2", "inst": "i2", "model": "m", "status": "COMPLETED", "passed": False, "score": 0.0},
        ],
    )
    result = compare_runs(base, cand)
    assert "m::i1" in result["improved"]
    assert "m::i2" in result["regressed"]
    assert result["unchanged_count"] == 0


def test_regression_newly_unsupported() -> None:
    base = _run("base", [{"id": "t1", "inst": "i1", "model": "m", "status": "COMPLETED", "passed": True, "score": 5.0}])
    cand = _run("cand", [{"id": "t1", "inst": "i1", "model": "m", "status": "UNSUPPORTED"}])
    result = compare_runs(base, cand)
    assert "m::i1" in result["newly_unsupported"]


def test_grouped_split_no_overlap() -> None:
    groups = [f"session_{i}" for i in range(10)]
    split = grouped_split(groups, ratios=(0.6, 0.2, 0.2), seed=0)
    assert set(split["train"]) | set(split["val"]) | set(split["test"]) == set(groups)
    leak = check_leakage(set(split["train"]), set(split["val"]), set(split["test"]))
    assert leak["leaked"] is False


def test_grouped_split_detects_leak() -> None:
    leak = check_leakage({"a", "b"}, {"b", "c"}, {"d"})
    assert leak["leaked"] is True
    assert "b" in leak["overlap"]["train_val"]
