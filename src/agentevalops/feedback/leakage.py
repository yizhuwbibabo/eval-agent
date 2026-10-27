"""Dataset leakage checks.

Train / validation / held-out eval sets must be split by source session or task
so that highly similar variants of the same failure do not straddle the split.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def grouped_split(
    group_ids: Iterable[str],
    ratios: tuple[float, float, float] = (0.8, 0.1, 0.1),
    seed: int = 0,
) -> dict[str, list[str]]:
    """Split *groups* (not instances) into train/val/test by ratio."""
    groups = sorted(set(group_ids))
    # Deterministic shuffle.
    import random

    rng = random.Random(seed)
    rng.shuffle(groups)
    n = len(groups)
    n_train = int(round(n * ratios[0]))
    n_val = int(round(n * ratios[1]))
    return {
        "train": groups[:n_train],
        "val": groups[n_train : n_train + n_val],
        "test": groups[n_train + n_val :],
    }


def check_leakage(train_groups: set[str], val_groups: set[str], test_groups: set[str]) -> dict[str, Any]:
    overlap = {
        "train_val": sorted(train_groups & val_groups),
        "train_test": sorted(train_groups & test_groups),
        "val_test": sorted(val_groups & test_groups),
    }
    return {
        "leaked": any(overlap.values()),
        "overlap": overlap,
        "sizes": {"train": len(train_groups), "val": len(val_groups), "test": len(test_groups)},
    }
