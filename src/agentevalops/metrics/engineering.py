"""Engineering / reliability metrics.

API errors, grader failures, invalid samples and model-behavior errors are
counted separately - never all folded into "model failure".
"""

from __future__ import annotations

from typing import Any

from agentevalops.schemas.evaluation import TrialResult, TrialStatus
from agentevalops.schemas.grading import GradeStatus, GradingResult

# Rough per-token cost model used only for estimates; mock models cost 0.
COST_PER_INPUT_TOKEN = 0.000001
COST_PER_OUTPUT_TOKEN = 0.000003


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    if n == 1:
        return s[0]
    rank = p * (n - 1)
    lo = int(rank)
    hi = min(lo + 1, n - 1)
    frac = rank - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def engineering_metrics(trials: list[TrialResult], gradings: list[GradingResult]) -> dict[str, Any]:
    completed = [t for t in trials if t.status == TrialStatus.COMPLETED and t.latency_ms is not None]
    latencies = [t.latency_ms or 0.0 for t in completed]

    input_tokens = sum(t.usage.input_tokens for t in trials if t.usage is not None)
    output_tokens = sum(t.usage.output_tokens for t in trials if t.usage is not None)
    estimated_cost = input_tokens * COST_PER_INPUT_TOKEN + output_tokens * COST_PER_OUTPUT_TOKEN

    infra_failed = [t for t in trials if t.status == TrialStatus.FAILED]
    api_error_rate = len(infra_failed) / len(trials) if trials else 0.0
    timeout_rate = (
        sum(1 for t in infra_failed if t.error_code == "TIMEOUT") / len(trials) if trials else 0.0
    )

    graded = [g for g in gradings if g.hybrid is not None]
    grader_failure_rate = (
        sum(1 for g in graded if g.hybrid and g.hybrid.status == GradeStatus.ERROR) / len(graded)
        if graded
        else 0.0
    )

    return {
        "latency_mean_ms": (sum(latencies) / len(latencies)) if latencies else None,
        "latency_p50_ms": _percentile(latencies, 0.50),
        "latency_p95_ms": _percentile(latencies, 0.95),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost": round(estimated_cost, 6),
        "cost_model": {"input_per_token": COST_PER_INPUT_TOKEN, "output_per_token": COST_PER_OUTPUT_TOKEN},
        "api_error_rate": api_error_rate,
        "timeout_rate": timeout_rate,
        "grader_failure_rate": grader_failure_rate,
        "throughput_trials_per_second": None,  # requires wall-clock run timing
    }
