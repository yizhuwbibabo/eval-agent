"""Evidence-driven failure diagnosis engine.

Produces a structured :class:`FailureDiagnosis` that separates what was
observed from what is inferred or hypothesized, and never fabricates a root
cause. Model behavior failures are explicitly marked as such; infrastructure,
harness, evaluator and data problems are classified separately.
"""

from __future__ import annotations

from agentevalops.diagnostics.remediation import remediation_for
from agentevalops.schemas.benchmark import BenchmarkInstance
from agentevalops.schemas.diagnosis import (
    DiagnosticEvidence,
    EvidenceStrength,
    FailureCategory,
    FailureDiagnosis,
    ReviewStatus,
)
from agentevalops.schemas.evaluation import TrialResult, TrialStatus
from agentevalops.schemas.grading import GradeStatus, GradingResult

CRITERION_CATEGORY: dict[str, FailureCategory] = {
    "error_correction_applied": FailureCategory.MODEL_BEHAVIOR_ERROR_RECOVERY_FAILURE,
    "no_repeat_of_failing_operation": FailureCategory.MODEL_BEHAVIOR_ERROR_RECOVERY_FAILURE,
    "log_inspection_before_retry": FailureCategory.MODEL_BEHAVIOR_MISSING_PREREQUISITE_CHECK,
    "no_uninformed_retry": FailureCategory.MODEL_BEHAVIOR_MISSING_PREREQUISITE_CHECK,
    "verification_before_claim": FailureCategory.MODEL_BEHAVIOR_UNSUPPORTED_SUCCESS_CLAIM,
    "no_ungrounded_success_claim": FailureCategory.MODEL_BEHAVIOR_UNSUPPORTED_SUCCESS_CLAIM,
    "confirmation_before_destructive_action": FailureCategory.MODEL_BEHAVIOR_UNSAFE_ACTION,
    "no_unauthorized_destructive_action": FailureCategory.MODEL_BEHAVIOR_UNSAFE_ACTION,
}

OVERRIDE_CATEGORY: dict[str, FailureCategory] = {
    "tool_name_validity": FailureCategory.MODEL_BEHAVIOR_WRONG_TOOL_SELECTION,
    "tool_argument_required_fields": FailureCategory.MODEL_BEHAVIOR_INVALID_TOOL_ARGUMENTS,
}

INFRA_CATEGORY: dict[str, FailureCategory] = {
    "TIMEOUT": FailureCategory.ENVIRONMENT_NETWORK_FAILURE,
    "RATE_LIMIT": FailureCategory.ENVIRONMENT_NETWORK_FAILURE,
    "PROVIDER_UNAVAILABLE": FailureCategory.ENVIRONMENT_TOOL_UNAVAILABLE,
    "PROVIDER_ERROR": FailureCategory.ENVIRONMENT_DEPENDENCY_FAILURE,
    "UNEXPECTED": FailureCategory.HARNESS_TOOL_ORCHESTRATION_ERROR,
}

_MODEL_ROOT_CAUSE_NOTE = (
    "A model behavior failure was observed. The available evidence does not "
    "establish whether the underlying cause is training data, prompt design, or "
    "another model-side factor."
)


def _fact(evidence_id: str, statement: str, event_ids: list[str]) -> DiagnosticEvidence:
    return DiagnosticEvidence(
        evidence_id=evidence_id,
        statement=statement,
        strength=EvidenceStrength.OBSERVED_FACT,
        event_ids=event_ids,
        source="trace",
    )


class DiagnosisEngine:
    def diagnose(
        self,
        instance: BenchmarkInstance,
        trial: TrialResult,
        grading: GradingResult | None = None,
    ) -> FailureDiagnosis | None:
        """Return a diagnosis for a non-passing trial, or None for a pass."""
        base = dict(
            diagnosis_id=f"DIAG::{trial.trial_id}",
            run_id=trial.run_id,
            instance_id=instance.instance_id,
            model_id=trial.model_id,
            behavior_id=instance.behavior_id,
            metadata={"frame": instance.frame.value, "cut_event_id": instance.cut_event_id},
        )

        if trial.status == TrialStatus.COMPLETED:
            return self._diagnose_completed(base, instance, trial, grading)

        if trial.status == TrialStatus.UNSUPPORTED:
            return FailureDiagnosis(
                **base,
                failed=False,
                primary_category=FailureCategory.HARNESS_TOOL_SCHEMA_MISMATCH,
                evidence=[
                    _fact("ev_unsupported", f"provider reported unsupported capability: {trial.error or ''}", [])
                ],
                root_cause_confirmable=True,
                root_cause_note="Model provider does not support the required tool-calling contract; not scored as a model failure.",
                remediation=remediation_for(FailureCategory.HARNESS_TOOL_SCHEMA_MISMATCH),
            )

        if trial.status == TrialStatus.FAILED:
            category = INFRA_CATEGORY.get(trial.error_code or "", FailureCategory.HARNESS_TOOL_ORCHESTRATION_ERROR)
            return FailureDiagnosis(
                **base,
                failed=False,
                primary_category=category,
                evidence=[
                    _fact("ev_infra", f"infrastructure error {trial.error_code}: {trial.error or ''}", [])
                ],
                root_cause_confirmable=True,
                root_cause_note="Infrastructure failure observed; not a model behavior failure.",
                remediation=remediation_for(category),
            )

        return None  # PENDING / CANCELLED trials are not diagnosed

    def _diagnose_completed(self, base: dict, instance: BenchmarkInstance, trial: TrialResult, grading: GradingResult | None) -> FailureDiagnosis | None:
        if grading is None:
            return FailureDiagnosis(
                **base,
                failed=False,
                primary_category=FailureCategory.UNKNOWN_INSUFFICIENT_EVIDENCE,
                evidence=[_fact("ev_nograde", "trial completed but has no grading result", [])],
                root_cause_confirmable=False,
                root_cause_note="No grading result available.",
                remediation=remediation_for(FailureCategory.UNKNOWN_INSUFFICIENT_EVIDENCE),
            )

        hybrid = grading.hybrid
        if hybrid is None:
            return FailureDiagnosis(
                **base,
                failed=False,
                primary_category=FailureCategory.UNKNOWN_INSUFFICIENT_EVIDENCE,
                evidence=[_fact("ev_nohybrid", "no hybrid verdict computed", [])],
                root_cause_confirmable=False,
                remediation=remediation_for(FailureCategory.UNKNOWN_INSUFFICIENT_EVIDENCE),
            )

        if hybrid.status == GradeStatus.ERROR:
            return FailureDiagnosis(
                **base,
                failed=False,
                primary_category=FailureCategory.EVALUATOR_GRADER_EXECUTION_ERROR,
                evidence=[_fact("ev_grader", "grader reported an execution error", [])],
                root_cause_confirmable=True,
                root_cause_note="Grader failure; the model response was not judged.",
                remediation=remediation_for(FailureCategory.EVALUATOR_GRADER_EXECUTION_ERROR),
            )

        if hybrid.status == GradeStatus.INSUFFICIENT_EVIDENCE:
            return FailureDiagnosis(
                **base,
                failed=False,
                primary_category=FailureCategory.UNKNOWN_INSUFFICIENT_EVIDENCE,
                evidence=[_fact("ev_insufficient", "insufficient evidence to score the response", [])],
                root_cause_confirmable=False,
                root_cause_note="Insufficient evidence; cannot reliably attribute this case.",
                remediation=remediation_for(FailureCategory.UNKNOWN_INSUFFICIENT_EVIDENCE),
            )

        if hybrid.passed:
            return None

        # A graded FAIL - determine the model behavior failure category.
        primary = self._primary_category(grading)
        contributing = self._contributing(grading, primary)
        evidence = self._instance_evidence(instance) + self._evidence(grading)
        hypotheses = [
            "Underlying cause (training data, prompt design, or model capability) cannot be confirmed from behavior observations alone."
        ]
        return FailureDiagnosis(
            **base,
            failed=True,
            primary_category=primary,
            contributing_factors=contributing,
            evidence=evidence,
            hypotheses=hypotheses,
            root_cause_confirmable=False,
            root_cause_note=_MODEL_ROOT_CAUSE_NOTE,
            remediation=remediation_for(primary),
            review_status=ReviewStatus.PENDING_HUMAN_REVIEW,
        )

    def _instance_evidence(self, instance: BenchmarkInstance) -> list[DiagnosticEvidence]:
        out: list[DiagnosticEvidence] = []
        meta = instance.cut_metadata
        cut_id = meta.get("cut_event_id")
        if cut_id:
            out.append(_fact("ev_cut", f"decision point cut at event {cut_id}", [cut_id]))
        for key, desc in [
            ("error_event_id", "tool error observed"),
            ("failure_event_id", "failure observed"),
            ("target_event_id", "target action/claim observed"),
        ]:
            eid = meta.get(key)
            if eid:
                out.append(_fact(f"ev_{key}", f"{desc} at event {eid}", [eid]))
        for eid in instance.evidence_references:
            out.append(_fact("ev_ref", f"confirmed evidence event {eid}", [eid]))
        return out

    def _primary_category(self, grading: GradingResult) -> FailureCategory:
        override = grading.hybrid.overridden_by if grading.hybrid else None
        if override and override in OVERRIDE_CATEGORY:
            return OVERRIDE_CATEGORY[override]
        for criterion_id in (grading.rubric_verdict.violated_criteria if grading.rubric_verdict else []):
            if criterion_id in CRITERION_CATEGORY:
                return CRITERION_CATEGORY[criterion_id]
        return FailureCategory.MODEL_BEHAVIOR_INSTRUCTION_VIOLATION

    def _contributing(self, grading: GradingResult, primary: FailureCategory) -> list[FailureCategory]:
        factors: list[FailureCategory] = []
        for hit in grading.deterministic_hits:
            if not hit.matched:
                continue
            if hit.rule_id in OVERRIDE_CATEGORY and OVERRIDE_CATEGORY[hit.rule_id] not in factors:
                factors.append(OVERRIDE_CATEGORY[hit.rule_id])
            if hit.rule_id in CRITERION_CATEGORY and CRITERION_CATEGORY[hit.rule_id] not in factors:
                factors.append(CRITERION_CATEGORY[hit.rule_id])
        # Keep primary first, others after, no duplicates.
        ordered = [primary] + [f for f in factors if f != primary]
        return ordered[:5]

    def _evidence(self, grading: GradingResult) -> list[DiagnosticEvidence]:
        evidence: list[DiagnosticEvidence] = []
        for i, hit in enumerate(grading.deterministic_hits):
            if not hit.matched:
                continue
            evidence.append(
                _fact(f"ev_rule_{i}", f"deterministic rule {hit.rule_id!r} matched: {hit.message}", hit.evidence_event_ids)
            )
        if grading.rubric_verdict:
            for e in grading.rubric_verdict.evidence:
                evidence.append(
                    DiagnosticEvidence(
                        evidence_id=f"ev_judge_{e.event_id or id(e)}",
                        statement=e.description,
                        strength=EvidenceStrength.OBSERVED_FACT,
                        event_ids=[e.event_id] if e.event_id else [],
                        source="grader",
                    )
                )
        evidence.append(
            DiagnosticEvidence(
                evidence_id="ev_category",
                statement="failure category assigned from observed rule and rubric violations",
                strength=EvidenceStrength.SUPPORTED_INFERENCE,
                event_ids=[],
                source="grader",
            )
        )
        return evidence
