"""Bootstrap confidence intervals for pass rates (benchmark-grouped).

When sample counts are too small the interval is wide and the caller should
state that conclusions are unstable.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from typing import Any


def bootstrap_ci(values: Sequence[float], n_bootstrap: int = 1000, seed: int = 0, alpha: float = 0.05) -> dict[str, Any]:
    if not values:
        return {"mean": None, "ci_low": None, "ci_high": None, "n": 0}
    rng = random.Random(seed)
    n = len(values)
    means: list[float] = []
    for _ in range(n_bootstrap):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    low_idx = int(round((alpha / 2) * (len(means) - 1)))
    high_idx = int(round((1 - alpha / 2) * (len(means) - 1)))
    return {
        "mean": sum(values) / n,
        "ci_low": means[low_idx],
        "ci_high": means[high_idx],
        "n": n,
        "n_bootstrap": n_bootstrap,
    }


def paired_pass_rate_ci(
    per_instance_pairs: list[tuple[bool, bool]], n_bootstrap: int = 1000, seed: int = 0
) -> dict[str, Any]:
    """Bootstrap CI on the difference in pass rates over paired instances.

    ``per_instance_pairs`` is a list of ``(model_a_passed, model_b_passed)``
    for instances evaluated under both models.
    """
    if not per_instance_pairs:
        return {"diff_mean": None, "ci_low": None, "ci_high": None, "n": 0}
    rng = random.Random(seed)
    n = len(per_instance_pairs)
    diffs: list[float] = []
    for _ in range(n_bootstrap):
        sample = [per_instance_pairs[rng.randrange(n)] for _ in range(n)]
        pa = sum(1 for a, _ in sample if a) / n
        pb = sum(1 for _, b in sample if b) / n
        diffs.append(pa - pb)
    diffs.sort()
    low_idx = int(round(0.025 * (len(diffs) - 1)))
    high_idx = int(round(0.975 * (len(diffs) - 1)))
    pa = sum(1 for a, _ in per_instance_pairs if a) / n
    pb = sum(1 for _, b in per_instance_pairs if b) / n
    return {
        "diff_mean": pa - pb,
        "ci_low": diffs[low_idx],
        "ci_high": diffs[high_idx],
        "n": n,
    }
