"""Reporting integration tests."""

from __future__ import annotations

import json

from agentevalops.benchmark.builder import BenchmarkBuilder
from agentevalops.config.settings import ExecutionConfig, GenerationConfig, ModelSpec
from agentevalops.diagnostics.engine import DiagnosisEngine
from agentevalops.evaluation.models import ModelRegistry
from agentevalops.evaluation.runner import EvalRunner
from agentevalops.grading.deterministic import evaluate_deterministic
from agentevalops.grading.hybrid import merge
from agentevalops.grading.llm_judge import MockRubricJudge
from agentevalops.reporting.data import RunArtifacts
from agentevalops.reporting.writer import write_report
from agentevalops.schemas.benchmark import BenchmarkDataset
from agentevalops.schemas.evaluation import EvalRun, RunStatus


def _artifacts(registry, traces):
    builder = BenchmarkBuilder(registry)
    instances = []
    for bid in registry.ids():
        instances.extend(builder.build(traces, bid, "b", "v1").dataset.instances)
    ds = BenchmarkDataset(benchmark_id="b", dataset_version="v1", instances=instances)
    by_id = {i.instance_id: i for i in instances}
    models = [
        ModelSpec(id="model_a", provider_model="mock/compliant"),
        ModelSpec(id="model_b", provider_model="mock/error_prone"),
    ]
    import asyncio

    outcome = asyncio.run(EvalRunner(ModelRegistry(), ExecutionConfig(concurrency=2), GenerationConfig()).run(ds, models, "r", 1))
    judge = MockRubricJudge()
    engine = DiagnosisEngine()
    gradings = []
    diagnoses = []
    for t in outcome.trials:
        inst = by_id[t.instance_id]
        hits = evaluate_deterministic(inst, t.response)
        verdict = judge._grade_sync(inst, t.response, registry.get(inst.behavior_id).rubric)
        hybrid = merge(hits, verdict, "hybrid", 4.0)
        from agentevalops.schemas.grading import GradingResult

        g = GradingResult(
            trial_id=t.trial_id,
            run_id="r",
            instance_id=inst.instance_id,
            model_id=t.model_id,
            behavior_id=inst.behavior_id,
            deterministic_hits=hits,
            rubric_verdict=verdict,
            hybrid=hybrid,
        )
        gradings.append(g)
        d = engine.diagnose(inst, t, g)
        if d:
            diagnoses.append(d)

    run = EvalRun(run_id="r", benchmark_id="b", dataset_version="v1", status=RunStatus.COMPLETED, models=["model_a", "model_b"])
    behaviors = {b.behavior_id: b for b in registry.all()}
    return RunArtifacts(run=run, trials=outcome.trials, gradings=gradings, diagnoses=diagnoses, instances=by_id, behaviors=behaviors)


def test_markdown_report(registry, traces, tmp_path) -> None:
    write_report(_artifacts(registry, traces), tmp_path)
    content = (tmp_path / "r" / "summary.md").read_text()
    assert "# Agent Failure Analysis Report" in content
    assert "model_a" in content and "model_b" in content
    assert "MODEL_BEHAVIOR.ERROR_RECOVERY_FAILURE" in content


def test_html_report(registry, traces, tmp_path) -> None:
    write_report(_artifacts(registry, traces), tmp_path)
    content = (tmp_path / "r" / "detailed_report.html").read_text()
    assert "<html" in content
    assert "Failure Cases" in content


def test_metrics_json_schema(registry, traces, tmp_path) -> None:
    write_report(_artifacts(registry, traces), tmp_path)
    data = json.loads((tmp_path / "r" / "metrics.json").read_text())
    assert "summary" in data
    assert "evaluation" in data
    assert "engineering" in data
    assert "failure_cases" in data


def test_failure_cases_jsonl_evidence_traceable(registry, traces, tmp_path) -> None:
    write_report(_artifacts(registry, traces), tmp_path)
    lines = (tmp_path / "r" / "failure_cases.jsonl").read_text().splitlines()
    assert len(lines) == 4  # model_b fails all 4 behaviors
    for line in lines:
        case = json.loads(line)
        assert case["model_id"] == "model_b"
        assert case["verdict"] == "FAIL"
        # evidence must be present and reference event ids
        assert case["evidence"]
        assert any(e.get("event_ids") for e in case["evidence"])


def test_model_comparison_csv(registry, traces, tmp_path) -> None:
    write_report(_artifacts(registry, traces), tmp_path)
    csv = (tmp_path / "r" / "model_comparison.csv").read_text()
    assert "model_a" in csv and "model_b" in csv
    assert "overall_pass_rate" in csv
