"""Hybrid grading merge strategies.

Hard-constraint violations (undefined tools, invalid arguments, unsafe actions)
always override a higher semantic score. Insufficient evidence is reported as
unscorable rather than defaulting to a pass.
"""

from __future__ import annotations

from agentevalops.grading.deterministic import hard_violations
from agentevalops.schemas.grading import (
    DeterministicHit,
    GraderVerdict,
    GradeStatus,
    HybridVerdict,
)


def merge(
    deterministic_hits: list[DeterministicHit],
    rubric_verdict: GraderVerdict | None,
    strategy: str,
    pass_threshold: float,
) -> HybridVerdict:
    components = [rubric_verdict] if rubric_verdict is not None else []
    hard = hard_violations(deterministic_hits)

    if hard:
        return HybridVerdict(
            final_score=0.0,
            passed=False,
            strategy=strategy,
            components=components,
            overridden_by=hard[0].rule_id,
            status=GradeStatus.GRADED,
        )

    if rubric_verdict is None:
        return HybridVerdict(
            final_score=None,
            passed=None,
            strategy=strategy,
            components=components,
            status=GradeStatus.INSUFFICIENT_EVIDENCE,
        )

    if rubric_verdict.status == GradeStatus.INSUFFICIENT_EVIDENCE:
        return HybridVerdict(
            final_score=None,
            passed=None,
            strategy=strategy,
            components=components,
            status=GradeStatus.INSUFFICIENT_EVIDENCE,
        )

    if rubric_verdict.status == GradeStatus.ERROR:
        return HybridVerdict(
            final_score=None,
            passed=None,
            strategy=strategy,
            components=components,
            status=GradeStatus.ERROR,
        )

    score = rubric_verdict.score
    passed = score is not None and score >= pass_threshold
    return HybridVerdict(
        final_score=score,
        passed=passed,
        strategy=strategy,
        components=components,
        status=GradeStatus.GRADED,
    )
