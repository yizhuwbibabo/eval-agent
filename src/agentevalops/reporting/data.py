"""Report data assembly.

Collects a run's artifacts into one structured, JSON-serializable document that
the Markdown, HTML and JSON renderers share.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentevalops.diagnostics.taxonomy import humanize
from agentevalops.metrics.engineering import engineering_metrics
from agentevalops.metrics.evaluation import evaluation_metrics
from agentevalops.schemas.behavior import BehaviorSpecification
from agentevalops.schemas.benchmark import BenchmarkInstance
from agentevalops.schemas.diagnosis import FailureCategory, FailureDiagnosis
from agentevalops.schemas.evaluation import EvalRun, TrialResult, TrialStatus
from agentevalops.schemas.grading import GradingResult


@dataclass
class RunArtifacts:
    run: EvalRun
    trials: list[TrialResult]
    gradings: list[GradingResult]
    diagnoses: list[FailureDiagnosis]
    instances: dict[str, BenchmarkInstance] = field(default_factory=dict)
    behaviors: dict[str, BehaviorSpecification] = field(default_factory=dict)
    build_stats: dict[str, Any] = field(default_factory=dict)
    config: Any = None


def _observed(trial: TrialResult) -> str:
    if trial.response is None:
        return trial.error or "(no response)"
    parts = []
    if trial.response.text:
        parts.append(trial.response.text)
    for c in trial.response.tool_calls:
        parts.append(f"{c.tool_name}({c.arguments})")
    return "; ".join(parts) if parts else "(empty response)"


def _failure_case(
    trial: TrialResult, grading: GradingResult, diagnosis: FailureDiagnosis, behaviors: dict[str, BehaviorSpecification]
) -> dict[str, Any]:
    behavior = behaviors.get(diagnosis.behavior_id)
    hybrid = grading.hybrid
    verdict = "FAIL" if hybrid and hybrid.passed is False else "UNKNOWN"
    score = hybrid.final_score if hybrid else None
    return {
        "case_id": diagnosis.diagnosis_id,
        "model_id": diagnosis.model_id,
        "behavior_id": diagnosis.behavior_id,
        "behavior_name": behavior.name if behavior else diagnosis.behavior_id,
        "frame": diagnosis.metadata.get("frame"),
        "expected": behavior.description if behavior else "",
        "observed": _observed(trial),
        "verdict": verdict,
        "score": score,
        "primary_category": diagnosis.primary_category.value,
        "contributing_factors": [c.value for c in diagnosis.contributing_factors],
        "evidence": [e.model_dump(mode="json") for e in diagnosis.evidence],
        "root_cause_confirmable": diagnosis.root_cause_confirmable,
        "root_cause_note": diagnosis.root_cause_note,
        "remediation": [r.model_dump(mode="json") for r in diagnosis.remediation],
        "review_status": diagnosis.review_status.value,
        "instance_id": diagnosis.instance_id,
        "trial_id": trial.trial_id,
    }


def assemble_report_data(artifacts: RunArtifacts) -> dict[str, Any]:
    run = artifacts.run
    trials = artifacts.trials
    gradings = artifacts.gradings
    diagnoses = artifacts.diagnoses

    grading_by_trial = {g.trial_id: g for g in gradings}
    trial_by_id = {t.trial_id: t for t in trials}

    eval_metrics = evaluation_metrics(trials, gradings)
    eng_metrics = engineering_metrics(trials, gradings)

    # Failure cases (non-passing trials with a diagnosis).
    failure_cases: list[dict[str, Any]] = []
    for d in diagnoses:
        trial = trial_by_id.get(d.diagnosis_id.removeprefix("DIAG::"))
        if trial is None:
            continue
        grading = grading_by_trial.get(trial.trial_id)
        failure_cases.append(_failure_case(trial, grading or GradingResult(
            trial_id=trial.trial_id, run_id=trial.run_id, instance_id=trial.instance_id,
            model_id=trial.model_id, behavior_id=trial.behavior_id,
        ), d, artifacts.behaviors))

    high_risk = [c for c in failure_cases if c["primary_category"].endswith("UNSAFE_ACTION")]

    from agentevalops.diagnostics.clustering import failure_distribution

    dist = failure_distribution(diagnoses)
    top_categories = [
        {"category": cat, "label": humanize(FailureCategory(cat)), "count": n}
        for cat, n in list(dist.items())[:5]
    ]

    recommendations: list[str] = []
    for c in failure_cases:
        for r in c["remediation"]:
            rec = f"[{r['target_module']}] {r['action']}"
            if rec not in recommendations:
                recommendations.append(rec)
    recommendations = recommendations[:10]

    [t for t in trials if t.status == TrialStatus.COMPLETED]
    graded_definite = [
        g for g in gradings
        if g.hybrid is not None and g.hybrid.passed is not None
    ]
    summary = {
        "run_id": run.run_id,
        "benchmark_id": run.benchmark_id,
        "dataset_version": run.dataset_version,
        "models": run.models,
        "total_trials": len(trials),
        "valid_trials": len(graded_definite),
        "invalid_trials": len([g for g in gradings if g.hybrid is not None and g.hybrid.passed is None]),
        "incomplete_trials": len([t for t in trials if t.status in (TrialStatus.FAILED, TrialStatus.UNSUPPORTED, TrialStatus.CANCELLED)]),
        "overall_pass_rate": eval_metrics["micro_pass_rate"],
        "top_failure_categories": top_categories,
        "high_risk_count": len(high_risk),
        "recommendations": recommendations,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }

    return {
        "summary": summary,
        "evaluation": eval_metrics,
        "engineering": eng_metrics,
        "failure_cases": failure_cases,
        "clusters": [{"category": k, "count": v} for k, v in dist.items()],
        "config": run.config_snapshot,
        "notes": [
            "Synthetic dataset: all traces are clearly marked dataset_source='synthetic'.",
            "Mock models: offline deterministic profiles, not real model API calls.",
        ],
    }
