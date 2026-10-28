"""Human-label sampling and ingestion tests."""

from __future__ import annotations

import json

from agentevalops.feedback.labeling import build_label_rows, ingest_labels, write_label_rows
from agentevalops.schemas.benchmark import BenchmarkInstance
from agentevalops.schemas.evaluation import AssistantTurn, ToolCall, TrialResult, TrialStatus, Usage
from agentevalops.schemas.grading import GradingResult, HybridVerdict


def _turn() -> AssistantTurn:
    return AssistantTurn(
        text="retrying the failed call",
        tool_calls=[ToolCall(call_id="c1", tool_name="send_email", arguments={})],
        finish_reason="tool_calls",
        usage=Usage(input_tokens=1, output_tokens=1, total_tokens=2),
    )


def _trial(trial_id: str) -> TrialResult:
    return TrialResult(
        trial_id=trial_id,
        run_id="r",
        instance_id=trial_id,
        model_id="m",
        behavior_id="b",
        status=TrialStatus.COMPLETED,
        response=_turn(),
    )


def _instance(instance_id: str) -> BenchmarkInstance:
    return BenchmarkInstance(
        benchmark_id="x",
        dataset_version="v1",
        instance_id=instance_id,
        behavior_id="b",
        frame="FAILURE",
        source_trace_id="t",
        cut_event_id="e",
        context=[],
        tool_definitions=[],
        rubric_id="rub",
        rubric_version="v1",
    )


def _grading(trial_id: str, passed: bool) -> GradingResult:
    return GradingResult(
        trial_id=trial_id,
        run_id="r",
        instance_id=trial_id,
        model_id="m",
        behavior_id="b",
        hybrid=HybridVerdict(passed=passed, strategy="hybrid"),
    )


def test_build_label_rows_stratifies(tmp_path) -> None:
    gradings = [_grading(f"t{i}", i % 2 == 0) for i in range(10)]  # 5 pass, 5 fail
    trials = {f"t{i}": _trial(f"t{i}") for i in range(10)}
    instances = {f"t{i}": _instance(f"t{i}") for i in range(10)}
    rows = build_label_rows(gradings, trials, instances, n=6, seed=42)
    assert len(rows) == 6
    labels = [r["label"] for r in rows]
    assert all(x is None for x in labels)
    passed = sum(1 for r in rows if r["grader_passed"])
    failed = sum(1 for r in rows if not r["grader_passed"])
    assert passed >= 1 and failed >= 1  # stratified: both sides represented


def test_ingest_labels_roundtrip(tmp_path) -> None:
    rows = [
        {"trial_id": "t1", "instance_id": "t1", "model_id": "m", "behavior_id": "b", "label": True, "notes": ""},
        {"trial_id": "t2", "instance_id": "t2", "model_id": "m", "behavior_id": "b", "label": False, "notes": ""},
        {"trial_id": "t3", "instance_id": "t3", "model_id": "m", "behavior_id": "b", "label": None, "notes": ""},
    ]
    path = tmp_path / "labels.jsonl"
    write_label_rows(rows, path)

    class FakeStore:
        def __init__(self):
            self.reviews = []

        def save_review(self, r):
            self.reviews.append(r)

    store = FakeStore()
    n = ingest_labels(store, "r", path)
    assert n == 2
    assert [r.label for r in store.reviews] == [True, False]
    assert json.loads(path.read_text().splitlines()[2])["label"] is None
