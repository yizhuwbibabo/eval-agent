"""Model comparison.

Only instances evaluated under the same valid conditions are compared. Paired
pass-rate differences are reported with a benchmark-grouped bootstrap interval
when the sample size allows.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from agentevalops.metrics.bootstrap import paired_pass_rate_ci
from agentevalops.metrics.engineering import COST_PER_INPUT_TOKEN, COST_PER_OUTPUT_TOKEN
from agentevalops.reporting.data import RunArtifacts
from agentevalops.schemas.evaluation import TrialStatus


def _per_model(artifacts: RunArtifacts) -> dict[str, dict[str, Any]]:
    trials = artifacts.trials
    gradings = artifacts.gradings
    grading_by_trial = {g.trial_id: g for g in gradings}
    models = sorted({t.model_id for t in trials})

    out: dict[str, dict[str, Any]] = {}
    for model in models:
        mt = [t for t in trials if t.model_id == model]
        gs = [
            grading_by_trial[t.trial_id]
            for t in mt
            if t.status == TrialStatus.COMPLETED and t.trial_id in grading_by_trial
        ]
        definite = [g for g in gs if g.hybrid is not None and g.hybrid.passed is not None]
        pass_rate = sum(1 for g in definite if g.hybrid and g.hybrid.passed) / len(definite) if definite else None

        per_behavior: dict[str, float | None] = {}
        for behavior in sorted({t.behavior_id for t in mt}):
            bgs = [g for g in gs if g.behavior_id == behavior and g.hybrid is not None and g.hybrid.passed is not None]
            per_behavior[behavior] = (
                sum(1 for g in bgs if g.hybrid and g.hybrid.passed) / len(bgs) if bgs else None
            )

        latencies = [t.latency_ms for t in mt if t.status == TrialStatus.COMPLETED and t.latency_ms is not None]
        in_tokens = sum(t.usage.input_tokens for t in mt if t.usage is not None)
        out_tokens = sum(t.usage.output_tokens for t in mt if t.usage is not None)
        cost = in_tokens * COST_PER_INPUT_TOKEN + out_tokens * COST_PER_OUTPUT_TOKEN
        api_errors = sum(1 for t in mt if t.status == TrialStatus.FAILED)

        out[model] = {
            "model_id": model,
            "pass_rate": pass_rate,
            "per_behavior": per_behavior,
            "latency_mean_ms": (sum(latencies) / len(latencies)) if latencies else None,
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "estimated_cost": round(cost, 6),
            "api_error_rate": api_errors / len(mt) if mt else 0.0,
            "trials": len(mt),
        }
    return out


def model_comparison_rows(artifacts: RunArtifacts) -> list[dict[str, Any]]:
    per_model = _per_model(artifacts)
    rows = list(per_model.values())
    # Paired differences vs the first model.
    if rows:
        baseline = rows[0]["model_id"]
        for row in rows:
            if row["model_id"] == baseline:
                row["paired_diff_vs_baseline"] = None
                row["paired_diff_ci"] = None
                continue
            diff, ci = _paired_diff(artifacts, baseline, row["model_id"])
            row["paired_diff_vs_baseline"] = diff
            row["paired_diff_ci"] = ci
    return rows


def _paired_diff(artifacts: RunArtifacts, model_a: str, model_b: str) -> tuple[float | None, dict[str, Any] | None]:
    grading_by_trial = {g.trial_id: g for g in artifacts.gradings}
    verdicts: dict[str, dict[str, bool | None]] = {}
    for t in artifacts.trials:
        if t.model_id not in (model_a, model_b) or t.status != TrialStatus.COMPLETED:
            continue
        g = grading_by_trial.get(t.trial_id)
        passed = g.hybrid.passed if g and g.hybrid else None
        verdicts.setdefault(t.instance_id, {})[t.model_id] = passed

    pairs: list[tuple[bool, bool]] = []
    for _inst, v in verdicts.items():
        a, b = v.get(model_a), v.get(model_b)
        if a is not None and b is not None:
            pairs.append((a, b))
    if not pairs:
        return None, None
    ci = paired_pass_rate_ci(pairs)
    return ci["diff_mean"], ci


def render_comparison_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    behavior_cols = sorted({b for r in rows for b in r["per_behavior"]})
    header = [
        "model",
        "overall_pass_rate",
        *[f"pass_rate_{b}" for b in behavior_cols],
        "latency_mean_ms",
        "input_tokens",
        "output_tokens",
        "estimated_cost",
        "api_error_rate",
        "paired_diff_vs_baseline",
    ]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow(
            [
                r["model_id"],
                r["pass_rate"],
                *[r["per_behavior"].get(b) for b in behavior_cols],
                r["latency_mean_ms"],
                r["input_tokens"],
                r["output_tokens"],
                r["estimated_cost"],
                r["api_error_rate"],
                r["paired_diff_vs_baseline"],
            ]
        )
    return buf.getvalue()
