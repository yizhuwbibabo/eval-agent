"""Benchmark construction metrics.

Each metric documents its numerator and denominator. Annotation agreement and
precision/recall are only reported when human labels exist.
"""

from __future__ import annotations

from typing import Any

from agentevalops.benchmark.builder import BuildStats


def construction_metrics(stats_by_behavior: dict[str, BuildStats]) -> dict[str, Any]:
    candidates = sum(s.candidate_count for s in stats_by_behavior.values())
    confirmed = sum(s.confirmed_count for s in stats_by_behavior.values())
    valid = sum(s.valid_instance_count for s in stats_by_behavior.values())
    invalid = sum(s.invalid_instance_count for s in stats_by_behavior.values())
    quarantined = sum(s.quarantined_count for s in stats_by_behavior.values())

    return {
        "candidate_count": candidates,  # total anchor recalls
        "confirmed_count": confirmed,
        "confirmation_rate": (confirmed / candidates) if candidates else 0.0,
        "valid_instance_rate": (valid / confirmed) if confirmed else 0.0,
        "build_success_rate": (valid / candidates) if candidates else 0.0,
        "invalid_instance_rate": ((invalid + quarantined) / confirmed) if confirmed else 0.0,
        "quarantined_count": quarantined,
        # Precision/recall/agreement require human labels; not computed here.
        "annotation_agreement": None,
        "per_behavior": {
            bid: {
                "candidate_count": s.candidate_count,
                "confirmation_rate": s.confirmation_rate,
                "valid_instance_rate": s.valid_instance_rate,
                "anchor_candidates": s.anchor_candidates,
            }
            for bid, s in sorted(stats_by_behavior.items())
        },
    }
