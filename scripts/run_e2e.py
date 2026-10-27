"""Run the complete offline end-to-end pipeline.

Usage: python scripts/run_e2e.py [--config configs/development.yaml]
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agentevalops.config import get_settings, load_eval_config  # noqa: E402
from agentevalops.logging_setup import setup_logging  # noqa: E402
from agentevalops.pipeline import Pipeline  # noqa: E402


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_json)
    config_path = sys.argv[sys.argv.index("--config") + 1] if "--config" in sys.argv else "configs/development.yaml"
    cfg = load_eval_config(config_path)

    pipeline = Pipeline(
        behaviors_dir="configs/behaviors",
        benchmark_root=settings.benchmark_root,
        artifact_root=settings.artifact_root,
        database_url=settings.database_url,
    )
    result = asyncio.run(
        pipeline.full(cfg, run_id="e2e_run", benchmark_id=cfg.evaluation.dataset, dataset_version=cfg.evaluation.dataset_version)
    )
    print("E2E complete. run_id:", result["run_id"])
    for kind, path in result["report_paths"].items():
        print(f"  {kind}: {path}")


if __name__ == "__main__":
    main()
