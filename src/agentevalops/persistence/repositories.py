"""Repositories: typed persistence for evaluation artifacts."""

from __future__ import annotations

from sqlalchemy import select

from agentevalops.persistence.db import Database
from agentevalops.persistence.models import (
    EvalRunRow,
    EvalTrialRow,
    FailureDiagnosisRow,
    FeedbackRecordRow,
    GradingResultRow,
    HumanReviewRow,
)
from agentevalops.schemas.diagnosis import FailureDiagnosis
from agentevalops.schemas.evaluation import EvalRun, TrialResult
from agentevalops.schemas.feedback import FeedbackRecord, HumanReview
from agentevalops.schemas.grading import GradingResult


class Store:
    """Saves and loads evaluation artifacts.

    Save methods are idempotent (upsert by natural key); original results are
    never silently overwritten with different payloads for the same key - the
    natural key is the identity of the artifact.
    """

    def __init__(self, database: Database) -> None:
        self.db = database

    # -- runs --------------------------------------------------------------- #
    def save_run(self, run: EvalRun) -> None:
        with self.db.session() as s:
            row = EvalRunRow(
                run_id=run.run_id,
                benchmark_id=run.benchmark_id,
                dataset_version=run.dataset_version,
                status=run.status.value,
                models=run.models,
                config_snapshot=run.config_snapshot,
                created_at=run.created_at,
                completed_at=run.completed_at,
                metadata_=run.metadata,
            )
            s.merge(row)
            s.commit()

    def get_run(self, run_id: str) -> EvalRun | None:
        with self.db.session() as s:
            row = s.get(EvalRunRow, run_id)
        if row is None:
            return None
        return EvalRun(
            run_id=row.run_id,
            benchmark_id=row.benchmark_id,
            dataset_version=row.dataset_version,
            status=row.status,  # type: ignore[arg-type]
            models=row.models or [],
            config_snapshot=row.config_snapshot or {},
            created_at=row.created_at,
            completed_at=row.completed_at,
            metadata=row.metadata_ or {},
        )

    def list_runs(self) -> list[str]:
        with self.db.session() as s:
            return list(s.scalars(select(EvalRunRow.run_id).order_by(EvalRunRow.created_at)).all())

    # -- trials ------------------------------------------------------------- #
    def save_trial(self, trial: TrialResult) -> None:
        with self.db.session() as s:
            row = EvalTrialRow(
                trial_id=trial.trial_id,
                run_id=trial.run_id,
                instance_id=trial.instance_id,
                model_id=trial.model_id,
                behavior_id=trial.behavior_id,
                status=trial.status.value,
                response=trial.response.model_dump(mode="json") if trial.response else None,
                error=trial.error,
                error_code=trial.error_code,
                latency_ms=trial.latency_ms,
                usage=trial.usage.model_dump(mode="json"),
                retries=trial.retries,
                metadata_=trial.metadata,
            )
            s.merge(row)
            s.commit()

    def get_trials(self, run_id: str) -> list[TrialResult]:
        from agentevalops.schemas.evaluation import AssistantTurn, TrialStatus, Usage

        with self.db.session() as s:
            rows = s.scalars(select(EvalTrialRow).where(EvalTrialRow.run_id == run_id)).all()
        out: list[TrialResult] = []
        for row in rows:
            response = None
            if row.response:
                response = AssistantTurn.model_validate(row.response)
            out.append(
                TrialResult(
                    trial_id=row.trial_id,
                    run_id=row.run_id,
                    instance_id=row.instance_id,
                    model_id=row.model_id,
                    behavior_id=row.behavior_id,
                    status=TrialStatus(row.status),
                    response=response,
                    error=row.error,
                    error_code=row.error_code,
                    latency_ms=row.latency_ms,
                    usage=Usage.model_validate(row.usage or {}),
                    retries=row.retries,
                    metadata=row.metadata_ or {},
                )
            )
        return out

    def get_trial(self, trial_id: str) -> TrialResult | None:
        trials = [t for t in self._all_trials() if t.trial_id == trial_id]
        return trials[0] if trials else None

    def completed_trial_ids(self, run_id: str) -> set[str]:
        with self.db.session() as s:
            rows = s.scalars(
                select(EvalTrialRow.trial_id).where(
                    EvalTrialRow.run_id == run_id,
                    EvalTrialRow.status.in_(["COMPLETED"]),
                )
            ).all()
        return set(rows)

    def _all_trials(self) -> list[TrialResult]:
        with self.db.session() as s:
            run_ids = list(s.scalars(select(EvalTrialRow.run_id)).all())
        out: list[TrialResult] = []
        for rid in set(run_ids):
            out.extend(self.get_trials(rid))
        return out

    # -- grading ------------------------------------------------------------ #
    def save_grading(self, g: GradingResult) -> None:
        with self.db.session() as s:
            row = GradingResultRow(
                trial_id=g.trial_id,
                run_id=g.run_id,
                instance_id=g.instance_id,
                model_id=g.model_id,
                behavior_id=g.behavior_id,
                deterministic_hits=[h.model_dump(mode="json") for h in g.deterministic_hits],
                rubric_verdict=g.rubric_verdict.model_dump(mode="json") if g.rubric_verdict else None,
                hybrid=g.hybrid.model_dump(mode="json") if g.hybrid else None,
                grader_version=g.grader_version,
            )
            s.merge(row)
            s.commit()

    def get_gradings(self, run_id: str) -> list[GradingResult]:
        from agentevalops.schemas.grading import (
            DeterministicHit,
            GraderVerdict,
            HybridVerdict,
        )

        with self.db.session() as s:
            rows = s.scalars(select(GradingResultRow).where(GradingResultRow.run_id == run_id)).all()
        out: list[GradingResult] = []
        for row in rows:
            out.append(
                GradingResult(
                    trial_id=row.trial_id,
                    run_id=row.run_id,
                    instance_id=row.instance_id,
                    model_id=row.model_id,
                    behavior_id=row.behavior_id,
                    deterministic_hits=[DeterministicHit.model_validate(h) for h in (row.deterministic_hits or [])],
                    rubric_verdict=GraderVerdict.model_validate(row.rubric_verdict) if row.rubric_verdict else None,
                    hybrid=HybridVerdict.model_validate(row.hybrid) if row.hybrid else None,
                    grader_version=row.grader_version,
                )
            )
        return out

    # -- diagnoses ---------------------------------------------------------- #
    def save_diagnosis(self, d: FailureDiagnosis) -> None:
        with self.db.session() as s:
            row = FailureDiagnosisRow(
                diagnosis_id=d.diagnosis_id,
                run_id=d.run_id,
                instance_id=d.instance_id,
                model_id=d.model_id,
                behavior_id=d.behavior_id,
                failed=d.failed,
                primary_category=d.primary_category.value,
                contributing_factors=[c.value for c in d.contributing_factors],
                evidence=[e.model_dump(mode="json") for e in d.evidence],
                hypotheses=d.hypotheses,
                root_cause_confirmable=d.root_cause_confirmable,
                root_cause_note=d.root_cause_note,
                remediation=[r.model_dump(mode="json") for r in d.remediation],
                review_status=d.review_status.value,
                metadata_=d.metadata,
            )
            s.merge(row)
            s.commit()

    def get_diagnoses(self, run_id: str) -> list[FailureDiagnosis]:
        from agentevalops.schemas.diagnosis import (
            DiagnosticEvidence,
            FailureCategory,
            RemediationAction,
            ReviewStatus,
        )

        with self.db.session() as s:
            rows = s.scalars(select(FailureDiagnosisRow).where(FailureDiagnosisRow.run_id == run_id)).all()
        out: list[FailureDiagnosis] = []
        for row in rows:
            out.append(
                FailureDiagnosis(
                    diagnosis_id=row.diagnosis_id,
                    run_id=row.run_id,
                    instance_id=row.instance_id,
                    model_id=row.model_id,
                    behavior_id=row.behavior_id,
                    failed=row.failed,
                    primary_category=FailureCategory(row.primary_category),
                    contributing_factors=[FailureCategory(c) for c in (row.contributing_factors or [])],
                    evidence=[DiagnosticEvidence.model_validate(e) for e in (row.evidence or [])],
                    hypotheses=row.hypotheses or [],
                    root_cause_confirmable=row.root_cause_confirmable,
                    root_cause_note=row.root_cause_note,
                    remediation=[RemediationAction.model_validate(r) for r in (row.remediation or [])],
                    review_status=ReviewStatus(row.review_status),
                    metadata=row.metadata_ or {},
                )
            )
        return out

    # -- reviews & feedback ------------------------------------------------- #
    def save_review(self, r: HumanReview) -> None:
        with self.db.session() as s:
            s.merge(
                HumanReviewRow(
                    review_id=r.review_id,
                    run_id=r.run_id,
                    instance_id=r.instance_id,
                    model_id=r.model_id,
                    reviewer=r.reviewer,
                    decision=r.decision.value,
                    label=r.label,
                    aspects=r.aspects,
                    notes=r.notes,
                    reviewed_at=r.reviewed_at,
                    version=r.version,
                )
            )
            s.commit()

    def get_reviews(self, run_id: str) -> list[HumanReview]:
        from agentevalops.schemas.feedback import ReviewDecision

        with self.db.session() as s:
            rows = s.scalars(select(HumanReviewRow).where(HumanReviewRow.run_id == run_id)).all()
        return [
            HumanReview(
                review_id=row.review_id,
                run_id=row.run_id,
                instance_id=row.instance_id,
                model_id=row.model_id,
                reviewer=row.reviewer,
                decision=ReviewDecision(row.decision),
                label=row.label,
                aspects=row.aspects or [],
                notes=row.notes,
                reviewed_at=row.reviewed_at,
                version=row.version,
            )
            for row in rows
        ]

    def save_feedback(self, f: FeedbackRecord) -> None:
        with self.db.session() as s:
            s.merge(
                FeedbackRecordRow(
                    record_id=f.record_id,
                    run_id=f.run_id,
                    instance_id=f.instance_id,
                    model_id=f.model_id,
                    behavior_id=f.behavior_id,
                    status=f.status.value,
                    review_id=f.review_id,
                    has_wrong_response=f.has_wrong_response,
                    has_verified_correct_response=f.has_verified_correct_response,
                    has_verified_preference_pair=f.has_verified_preference_pair,
                    metadata_=f.metadata,
                )
            )
            s.commit()

    def get_feedback(self, status: str | None = None) -> list[FeedbackRecord]:
        from agentevalops.schemas.feedback import FeedbackStatus

        with self.db.session() as s:
            q = select(FeedbackRecordRow)
            if status:
                q = q.where(FeedbackRecordRow.status == status)
            rows = s.scalars(q).all()
        return [
            FeedbackRecord(
                record_id=row.record_id,
                run_id=row.run_id,
                instance_id=row.instance_id,
                model_id=row.model_id,
                behavior_id=row.behavior_id,
                status=FeedbackStatus(row.status),
                review_id=row.review_id,
                has_wrong_response=row.has_wrong_response,
                has_verified_correct_response=row.has_verified_correct_response,
                has_verified_preference_pair=row.has_verified_preference_pair,
                metadata=row.metadata_ or {},
            )
            for row in rows
        ]
