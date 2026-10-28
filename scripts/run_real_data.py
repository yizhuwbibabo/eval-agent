"""Real-data end-to-end: import real recovery trajectories -> benchmark -> run.

This script runs the full AgentEvalOps pipeline against the public
``GurkanOz/tool-failure-recovery-trajectories`` dataset (train/recovery_v3.jsonl).

By default it uses deterministic offline mock models (no API key). To run real
models, pass a config that uses the ``openai_compat`` provider and export
``OPENAI_API_KEY`` (and optionally ``OPENAI_BASE_URL``):

    python scripts/run_real_data.py --config configs/production_recovery.yaml

Real models require OPENAI_API_KEY in the environment; this offline default
never fabricates real-model results.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agentevalops.benchmark.builder import BenchmarkBuilder  # noqa: E402
from agentevalops.config.settings import EvalConfig, get_settings, load_eval_config  # noqa: E402
from agentevalops.ingestion.openai_chat import OpenAIChatImporter  # noqa: E402
from agentevalops.logging_setup import setup_logging  # noqa: E402
from agentevalops.pipeline import Pipeline  # noqa: E402
from agentevalops.quality.report import build_quality_report  # noqa: E402


def _mock_config() -> EvalConfig:
    return EvalConfig.model_validate(
        {
            "evaluation": {"dataset": "recovery_v3", "dataset_version": "v1", "trials_per_instance": 1},
            "models": [
                {"id": "model_compliant", "provider_model": "mock/compliant"},
                {"id": "model_error_prone", "provider_model": "mock/error_prone"},
                {"id": "model_wrong_tool", "provider_model": "mock/wrong_tool"},
            ],
            "generation": {"temperature": 0, "max_output_tokens": 4096},
            "execution": {"concurrency": 8, "timeout_seconds": 30, "retry_attempts": 1, "retry_backoff_base": 0.01},
            "grading": {"strategy": "hybrid", "pass_threshold": 4.0, "judge": "mock", "judge_version": "v1"},
        }
    )


def _arg(flag: str, default: str | None = None) -> str | None:
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def main() -> None:
    settings = get_settings()
    settings.ensure_dirs()
    setup_logging(settings.log_level, settings.log_json)

    data_path = _arg("--data", "data/real/recovery_v3.jsonl")
    config_path = _arg("--config")
    limit_arg = _arg("--limit")
    limit = int(limit_arg) if limit_arg else None
    cfg = load_eval_config(config_path) if config_path else _mock_config()
    benchmark_id = cfg.evaluation.dataset
    dataset_version = cfg.evaluation.dataset_version

    # 1. Import real data into the unified Trace schema.
    imported = OpenAIChatImporter().import_file(data_path)
    traces = imported.traces
    if limit is not None:
        traces = traces[:limit]
    print(f"[import] traces={len(traces)} failed={len(imported.failed_records)} warnings={len(imported.warnings)}")

    # 2. Data quality gate.
    qr = build_quality_report(traces)
    print(
        f"[quality] total={qr.total} valid={qr.valid} partial={qr.partial} "
        f"invalid={qr.invalid} quarantined={qr.quarantined}"
    )
    # Quarantined traces (e.g. email-domain records whose tool arguments contain
    # PII-like email addresses) are excluded from benchmark construction so the
    # security gate is respected rather than bypassed.
    passed_ids = {tq.trace_id for tq in qr.per_trace if tq.status.value in ("VALID", "PARTIAL")}
    build_traces = [t for t in traces if t.trace_id in passed_ids]
    excluded = len(traces) - len(build_traces)
    if excluded:
        print(f"[quality] excluding {excluded} quarantined/invalid traces from benchmark construction")

    pipeline = Pipeline(
        behaviors_dir="configs/behaviors",
        benchmark_root=settings.benchmark_root,
        artifact_root=settings.artifact_root,
        database_url=settings.database_url,
    )

    # 3. Build the tool_failure_recovery benchmark from real traces.
    build = BenchmarkBuilder(pipeline.registry).build(
        build_traces, "tool_failure_recovery", benchmark_id, dataset_version, source_type="real"
    )
    print(
        f"[build] candidates={build.stats.candidate_count} confirmed={build.stats.confirmed_count} "
        f"instances={build.stats.valid_instance_count} rejected={build.stats.rejected_count} "
        f"insufficient={build.stats.insufficient_evidence_count} quarantined={build.stats.quarantined_count}"
    )
    pipeline.datasets.save(build.dataset, source_type="real")

    # 4. Run -> score -> analyze -> report.
    run_id = f"real_{benchmark_id}_run"
    outcome = asyncio.run(pipeline.run(cfg, run_id))
    print(f"[run] trials={len(outcome.trials)}")
    gradings = asyncio.run(pipeline.score(run_id, cfg))
    print(f"[score] gradings={len(gradings)}")
    diagnoses = pipeline.analyze(run_id)
    print(f"[analyze] diagnoses={len(diagnoses)}")
    paths = pipeline.report(run_id)
    for kind, path in paths.items():
        print(f"  {kind}: {path}")


if __name__ == "__main__":
    main()
