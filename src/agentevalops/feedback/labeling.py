"""Human-label sampling and ingestion for grader calibration.

A grader's agreement / kappa / precision / recall can only be measured against
human labels. This module produces a stratified labeling batch (so reviewers
see both passes and failures, not just diagnosed failures) and ingests the
filled labels back as :class:`HumanReview` records with an explicit pass/fail
``label``.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from agentevalops.schemas.benchmark import BenchmarkInstance
from agentevalops.schemas.evaluation import TrialResult
from agentevalops.schemas.feedback import HumanReview, ReviewDecision
from agentevalops.schemas.grading import GradingResult


def _summarize_context(instance: BenchmarkInstance) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in instance.context:
        out.append(
            {
                "role": m.role,
                "content": m.content or "",
                "tool_name": m.tool_name,
                "tool_arguments": m.tool_arguments,
                "tool_result": m.tool_result,
                "error": m.error,
            }
        )
    return out


def _summarize_response(trial: TrialResult) -> dict[str, Any]:
    if trial.response is None:
        return {"text": None, "tool_calls": [], "error": trial.error}
    return {
        "text": trial.response.text,
        "tool_calls": [
            {"name": c.tool_name, "arguments": c.arguments} for c in trial.response.tool_calls
        ],
    }


def build_label_rows(
    gradings: list[GradingResult],
    trials: dict[str, TrialResult],
    instances: dict[str, BenchmarkInstance],
    n: int,
    seed: int,
) -> list[dict[str, Any]]:
    """Stratify by grader pass/fail and sample up to ``n`` trials for labeling."""
    passed: list[GradingResult] = []
    failed: list[GradingResult] = []
    for g in gradings:
        if g.hybrid is None or g.hybrid.passed is None:
            continue
        if g.trial_id not in trials or g.instance_id not in instances:
            continue
        (passed if g.hybrid.passed else failed).append(g)

    rng = random.Random(seed)
    half = max(1, n // 2)
    picked = rng.sample(passed, min(half, len(passed))) + rng.sample(failed, min(n - half, len(failed)))
    rng.shuffle(picked)

    rows: list[dict[str, Any]] = []
    for g in picked:
        trial = trials[g.trial_id]
        inst = instances[g.instance_id]
        hy = g.hybrid
        assert hy is not None and hy.passed is not None
        rows.append(
            {
                "trial_id": g.trial_id,
                "instance_id": g.instance_id,
                "model_id": g.model_id,
                "behavior_id": g.behavior_id,
                "grader_passed": bool(hy.passed),
                "grader_score": hy.final_score,
                "context": _summarize_context(inst),
                "model_response": _summarize_response(trial),
                # Reviewer fills this: true (correct behavior) or false.
                "label": None,
            }
        )
    return rows


def write_label_rows(rows: list[dict[str, Any]], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def ingest_labels(store: Any, run_id: str, path: str | Path) -> int:
    """Read a filled label file and persist a HumanReview per labeled row."""
    count = 0
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get("label") is None:
            continue
        review = HumanReview(
            review_id=f"REV::{run_id}::{row['model_id']}::{row['instance_id']}::label",
            run_id=run_id,
            instance_id=row["instance_id"],
            model_id=row["model_id"],
            reviewer=row.get("reviewer", "human"),
            decision=ReviewDecision.CONFIRM,
            label=bool(row["label"]),
            aspects=["grader_correct"],
            notes=row.get("notes", ""),
        )
        store.save_review(review)
        count += 1
    return count
