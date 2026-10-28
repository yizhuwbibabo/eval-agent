"""Re-score an existing run with a (possibly different) judge.

Grading is decoupled from model execution, so saved responses can be re-scored
without re-running the models. The script skips trials already graded by a
model-based judge (``llm_rubric_judge``) so it can be run repeatedly to make
incremental progress on a large run within a bounded wall-clock.

Usage:
    JUDGE_API_KEY=... AGENTEVALOPS_ALLOW_EXTERNAL_RAW_TRACES=true \
      python scripts/rescore_with_judge.py \
        --run-id real_recovery_v3_run \
        --config configs/deepseek_recovery.yaml \
        --database-url sqlite:////tmp/deepseek.db \
        --benchmark-root .real_ds \
        --limit 60
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agentevalops.config.settings import get_settings, load_eval_config  # noqa: E402
from agentevalops.grading.rescore import score_trial  # noqa: E402
from agentevalops.logging_setup import setup_logging  # noqa: E402
from agentevalops.pipeline import Pipeline  # noqa: E402
from agentevalops.schemas.grading import GradeStatus  # noqa: E402


def _arg(flag: str, default: str | None = None) -> str | None:
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_json)

    run_id = _arg("--run-id") or "real_recovery_v3_run"
    config_path = _arg("--config")
    if not config_path:
        raise SystemExit("--config is required")
    cfg = load_eval_config(config_path)
    limit = int(_arg("--limit") or "0")

    pipeline = Pipeline(
        behaviors_dir="configs/behaviors",
        benchmark_root=_arg("--benchmark-root") or settings.benchmark_root,
        artifact_root=settings.artifact_root,
        database_url=_arg("--database-url") or settings.database_url,
    )
    assert pipeline.store is not None
    run = pipeline.store.get_run(run_id)
    if run is None:
        raise KeyError(f"unknown run {run_id!r}")
    trials = pipeline.store.get_trials(run_id)
    instances = pipeline._load_instances(run.benchmark_id, run.dataset_version)
    judge = pipeline._judge(cfg)

    already = {
        g.trial_id
        for g in pipeline.store.get_gradings(run_id)
        if g.rubric_verdict is not None
        and g.rubric_verdict.grader_id == "llm_rubric_judge"
        and g.rubric_verdict.status != GradeStatus.ERROR
    }
    todo = [t for t in trials if t.trial_id not in already]
    if limit:
        todo = todo[:limit]
    print(f"[rescore] {len(already)} already judged; {len(todo)} to score now", flush=True)

    sem = asyncio.Semaphore(max(1, cfg.grading.concurrency))

    async def one(trial):
        instance = instances.get(trial.instance_id)
        if instance is None:
            return None
        behavior = pipeline.registry.get(instance.behavior_id)
        async with sem:
            g = await score_trial(
                instance,
                trial,
                behavior.rubric,
                judge,
                cfg.grading.strategy,
                cfg.grading.pass_threshold,
                cfg.grading.judge_version,
            )
        pipeline.store.save_grading(g)
        return g

    async def run_all():
        return await asyncio.gather(*(one(t) for t in todo))

    done = [g for g in asyncio.run(run_all()) if g is not None]
    print(f"[rescore] scored {len(done)} trials with judge={cfg.grading.judge} ({cfg.grading.judge_model})", flush=True)


if __name__ == "__main__":
    main()
