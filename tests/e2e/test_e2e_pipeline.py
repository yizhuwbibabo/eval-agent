"""End-to-end pipeline test: traces -> report."""

from __future__ import annotations

import json

from agentevalops.config.settings import EvalConfig
from agentevalops.pipeline import Pipeline


def _config(behavior_dir: str) -> EvalConfig:
    return EvalConfig.model_validate(
        {
            "evaluation": {"dataset": "agent_behavior_v1", "dataset_version": "v1", "trials_per_instance": 1},
            "models": [
                {"id": "model_a", "provider_model": "mock/compliant"},
                {"id": "model_b", "provider_model": "mock/error_prone"},
            ],
            "generation": {"temperature": 0, "max_output_tokens": 4096},
            "execution": {"concurrency": 2, "timeout_seconds": 30, "retry_attempts": 1, "retry_backoff_base": 0.01},
            "grading": {"strategy": "hybrid", "pass_threshold": 4.0, "judge": "mock", "judge_version": "v1"},
        }
    )


def test_full_pipeline_offline(registry, traces, tmp_path, repo_root) -> None:
    import asyncio

    behaviors_dir = str(repo_root / "configs" / "behaviors")
    pipeline = Pipeline(
        behaviors_dir=behaviors_dir,
        benchmark_root=str(tmp_path / "datasets"),
        artifact_root=str(tmp_path / "reports"),
        database_url=f"sqlite:///{tmp_path}/e2e.db",
    )
    cfg = _config(behaviors_dir)
    result = asyncio.run(pipeline.full(cfg, run_id="e2e", traces=traces))
    assert result["run_id"] == "e2e"

    report_dir = tmp_path / "reports" / "e2e"
    assert (report_dir / "summary.md").exists()
    assert (report_dir / "detailed_report.html").exists()
    assert (report_dir / "metrics.json").exists()
    assert (report_dir / "failure_cases.jsonl").exists()
    assert (report_dir / "model_comparison.csv").exists()

    metrics = json.loads((report_dir / "metrics.json").read_text())
    by_model = metrics["evaluation"]["by_model"]
    assert by_model["model_a"]["pass_rate"] == 1.0
    assert by_model["model_b"]["pass_rate"] == 0.0

    failures = [json.loads(line) for line in (report_dir / "failure_cases.jsonl").read_text().splitlines()]
    assert all(f["model_id"] == "model_b" for f in failures)
    categories = {f["primary_category"] for f in failures}
    assert "MODEL_BEHAVIOR.UNSAFE_ACTION" in categories
    assert "MODEL_BEHAVIOR.ERROR_RECOVERY_FAILURE" in categories
