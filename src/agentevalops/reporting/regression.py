"""Regression comparison between two evaluation runs.

Instances are paired by ``(model_id, instance_id)``. If the model version,
dataset or scoring rules changed, that must be stated by the caller in the
report notes - the comparison itself only reports verdict deltas.
"""

from __future__ import annotations

from typing import Any

from agentevalops.reporting.data import RunArtifacts
from agentevalops.schemas.evaluation import TrialResult, TrialStatus


def _outcome(trial: TrialResult, grading_by_trial: dict[str, Any]) -> str:
    if trial.status == TrialStatus.UNSUPPORTED:
        return "unsupported"
    if trial.status == TrialStatus.FAILED:
        return "incomplete"
    g = grading_by_trial.get(trial.trial_id)
    if g is None or g.hybrid is None:
        return "invalid"
    if g.hybrid.status.value == "error":
        return "invalid"
    if g.hybrid.status.value == "insufficient_evidence":
        return "invalid"
    return "pass" if g.hybrid.passed else "fail"


def compare_runs(base: RunArtifacts, candidate: RunArtifacts) -> dict[str, Any]:
    base_grading = {g.trial_id: g for g in base.gradings}
    cand_grading = {g.trial_id: g for g in candidate.gradings}

    base_map = {(t.model_id, t.instance_id): _outcome(t, base_grading) for t in base.trials}
    cand_map = {(t.model_id, t.instance_id): _outcome(t, cand_grading) for t in candidate.trials}

    improved: list[str] = []
    regressed: list[str] = []
    unchanged: list[str] = []
    newly_invalid: list[str] = []
    newly_unsupported: list[str] = []
    newly_resolved: list[str] = []

    for key in sorted(set(base_map) | set(cand_map)):
        b, c = base_map.get(key), cand_map.get(key)
        label = f"{key[0]}::{key[1]}"
        if b is None and c is not None:
            continue  # new instance, not a regression
        if c is None and b is not None:
            continue
        if b == c:
            unchanged.append(label)
            continue
        if b in ("pass", "fail") and c in ("pass", "fail"):
            if b == "fail" and c == "pass":
                improved.append(label)
            elif b == "pass" and c == "fail":
                regressed.append(label)
            else:
                unchanged.append(label)
            continue
        if b in ("pass", "fail") and c == "invalid":
            newly_invalid.append(label)
            continue
        if c == "unsupported" and b != "unsupported":
            newly_unsupported.append(label)
            continue
        if b in ("fail", "invalid") and c == "pass":
            newly_resolved.append(label)
            continue
        unchanged.append(label)

    return {
        "baseline_run": base.run.run_id,
        "candidate_run": candidate.run.run_id,
        "improved": improved,
        "regressed": regressed,
        "unchanged_count": len(unchanged),
        "newly_invalid": newly_invalid,
        "newly_unsupported": newly_unsupported,
        "newly_resolved": newly_resolved,
        "paired_total": len(improved) + len(regressed) + len(unchanged),
    }
