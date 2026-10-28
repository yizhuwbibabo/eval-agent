"""Re-score an existing run with a (possibly different) judge.

Grading is decoupled from model execution, so saved responses can be re-scored
without re-running the models. This script loads a finished run's trials from
the store, re-scores them with the judge in the given config, and regenerates
the analysis + report bundle.

Usage:
    JUDGE_API_KEY=... AGENTEVALOPS_ALLOW_EXTERNAL_RAW_TRACES=true \
      python scripts/rescore_with_judge.py \
        --run-id real_recovery_v3_run \
        --config configs/deepseek_recovery.yaml \
        --database-url sqlite:////tmp/deepseek.db \
        --benchmark-root .real_ds
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agentevalops.config.settings import get_settings, load_eval_config  # noqa: E402
from agentevalops.logging_setup import setup_logging  # noqa: E402
from agentevalops.pipeline import Pipeline  # noqa: E402


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

    pipeline = Pipeline(
        behaviors_dir="configs/behaviors",
        benchmark_root=_arg("--benchmark-root") or settings.benchmark_root,
        artifact_root=settings.artifact_root,
        database_url=_arg("--database-url") or settings.database_url,
    )

    gradings = asyncio.run(pipeline.score(run_id, cfg))
    print(f"[score] re-scored {len(gradings)} trials with judge={cfg.grading.judge} ({cfg.grading.judge_model or 'mock'})")
    diagnoses = pipeline.analyze(run_id)
    print(f"[analyze] diagnoses={len(diagnoses)}")
    paths = pipeline.report(run_id)
    for kind, path in paths.items():
        print(f"  {kind}: {path}")


if __name__ == "__main__":
    main()
