"""Human review service.

Reviews update diagnoses and feedback records with versioning and audit
trail. Review decisions never silently mutate original evaluation results.
"""

from __future__ import annotations

from datetime import datetime, timezone

from agentevalops.persistence.repositories import Store
from agentevalops.schemas.diagnosis import FailureDiagnosis, ReviewStatus
from agentevalops.schemas.feedback import (
    FeedbackRecord,
    FeedbackStatus,
    HumanReview,
    ReviewDecision,
)


class ReviewService:
    def __init__(self, store: Store) -> None:
        self.store = store

    def submit(self, review: HumanReview, diagnoses: list[FailureDiagnosis]) -> FeedbackRecord | None:
        review.reviewed_at = review.reviewed_at or datetime.now(timezone.utc)
        self.store.save_review(review)

        # Update the matching diagnosis review status.
        for d in diagnoses:
            if d.instance_id == review.instance_id and d.model_id == review.model_id:
                d.review_status = ReviewStatus.REVIEWED
                self.store.save_diagnosis(d)

        record = self.store.get_feedback()
        existing = next(
            (r for r in record if r.instance_id == review.instance_id and r.model_id == review.model_id), None
        )
        if existing is None:
            return None

        status = FeedbackStatus.REJECTED
        if review.decision == ReviewDecision.CONFIRM:
            status = FeedbackStatus.HUMAN_CONFIRMED
            if review.notes.strip().lower().startswith("approve"):
                status = FeedbackStatus.APPROVED_FOR_TRAINING
        existing.status = status
        existing.review_id = review.review_id
        self.store.save_feedback(existing)
        return existing
