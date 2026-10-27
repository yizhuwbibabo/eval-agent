"""Grader calibration: agreement with human labels.

Only computed when human labels exist; never fabricates grader accuracy.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, Field


class CalibrationResult(BaseModel):
    agreement_rate: float | None = None
    cohens_kappa: float | None = None
    precision: float | None = None
    recall: float | None = None
    confusion: dict[str, int] = Field(default_factory=dict)
    n: int = 0
    note: str = ""


def _kappa(a: list[bool], b: list[bool]) -> float:
    n = len(a)
    if n == 0:
        return 0.0
    po = sum(1 for x, y in zip(a, b, strict=False) if x == y) / n
    p_yes_a = sum(a) / n
    p_yes_b = sum(b) / n
    pe = p_yes_a * p_yes_b + (1 - p_yes_a) * (1 - p_yes_b)
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def calibrate(auto_passed: Sequence[bool], human_passed: Sequence[bool]) -> CalibrationResult:
    n = len(auto_passed)
    if n == 0:
        return CalibrationResult(note="no labels provided")
    if len(auto_passed) != len(human_passed):
        return CalibrationResult(n=len(auto_passed), note="label length mismatch")

    tp = sum(1 for a, h in zip(auto_passed, human_passed, strict=False) if a and h)
    fp = sum(1 for a, h in zip(auto_passed, human_passed, strict=False) if a and not h)
    fn = sum(1 for a, h in zip(auto_passed, human_passed, strict=False) if not a and h)
    tn = sum(1 for a, h in zip(auto_passed, human_passed, strict=False) if not a and not h)

    agreement = (tp + tn) / n
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None

    return CalibrationResult(
        agreement_rate=round(agreement, 4),
        cohens_kappa=round(_kappa(list(auto_passed), list(human_passed)), 4),
        precision=round(precision, 4) if precision is not None else None,
        recall=round(recall, 4) if recall is not None else None,
        confusion={"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        n=n,
    )
