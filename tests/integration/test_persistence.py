"""Persistence integration tests."""

from __future__ import annotations

from datetime import datetime, timezone

from agentevalops.persistence import get_store
from agentevalops.schemas.diagnosis import FailureCategory, FailureDiagnosis
from agentevalops.schemas.evaluation import EvalRun, RunStatus
from agentevalops.schemas.grading import GradingResult


def test_run_trial_roundtrip(tmp_path) -> None:
    store = get_store(f"sqlite:///{tmp_path}/db.sqlite")
    run = EvalRun(
        run_id="r1",
        benchmark_id="b",
        dataset_version="v1",
        status=RunStatus.COMPLETED,
        models=["m"],
        config_snapshot={"x": 1},
        created_at=datetime.now(timezone.utc),
    )
    store.save_run(run)
    loaded = store.get_run("r1")
    assert loaded is not None
    assert loaded.models == ["m"]
    assert loaded.config_snapshot == {"x": 1}
    assert "r1" in store.list_runs()


def test_grading_and_diagnosis_roundtrip(tmp_path) -> None:
    store = get_store(f"sqlite:///{tmp_path}/db.sqlite")
    g = GradingResult(trial_id="t1", run_id="r1", instance_id="i1", model_id="m", behavior_id="b")
    store.save_grading(g)
    loaded = store.get_gradings("r1")
    assert len(loaded) == 1
    assert loaded[0].trial_id == "t1"

    d = FailureDiagnosis(
        diagnosis_id="d1",
        run_id="r1",
        instance_id="i1",
        model_id="m",
        behavior_id="b",
        failed=True,
        primary_category=FailureCategory.MODEL_BEHAVIOR_UNSAFE_ACTION,
        root_cause_confirmable=False,
    )
    store.save_diagnosis(d)
    loaded_d = store.get_diagnoses("r1")
    assert len(loaded_d) == 1
    assert loaded_d[0].primary_category == FailureCategory.MODEL_BEHAVIOR_UNSAFE_ACTION


def test_grading_rescore_overwrites_not_appends(tmp_path) -> None:
    """Re-scoring the same trial (e.g. with a different judge) must replace
    the previous grading rather than append a duplicate row."""
    store = get_store(f"sqlite:///{tmp_path}/db.sqlite")
    g1 = GradingResult(trial_id="t1", run_id="r1", instance_id="i1", model_id="m", behavior_id="b", grader_version="v1")
    g2 = GradingResult(trial_id="t1", run_id="r1", instance_id="i1", model_id="m", behavior_id="b", grader_version="v2")
    store.save_grading(g1)
    store.save_grading(g2)
    loaded = store.get_gradings("r1")
    assert len(loaded) == 1
    assert loaded[0].grader_version == "v2"


def test_completed_trial_ids(tmp_path) -> None:
    from agentevalops.schemas.evaluation import TrialResult, TrialStatus

    store = get_store(f"sqlite:///{tmp_path}/db.sqlite")
    store.save_run(EvalRun(run_id="r", benchmark_id="b", dataset_version="v1", status=RunStatus.RUNNING))
    store.save_trial(TrialResult(trial_id="t1", run_id="r", instance_id="i", model_id="m", behavior_id="b", status=TrialStatus.COMPLETED))
    store.save_trial(TrialResult(trial_id="t2", run_id="r", instance_id="i", model_id="m", behavior_id="b", status=TrialStatus.FAILED, error_code="TIMEOUT"))
    assert store.completed_trial_ids("r") == {"t1"}
