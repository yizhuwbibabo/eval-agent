"""Training-candidate export.

Only records with human verification are exported, and the export keeps wrong
responses, verified correct responses and verified preference pairs distinct.
Unverified grader output is never promoted to a training label.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentevalops.schemas.feedback import FeedbackRecord, FeedbackStatus


def export_training_candidates(
    records: list[FeedbackRecord],
    responses: dict[str, dict[str, Any]],
    path: str | Path,
) -> Path:
    """``responses`` maps record_id -> response payloads (wrong/correct as available)."""
    approved = [r for r in records if r.status == FeedbackStatus.APPROVED_FOR_TRAINING]
    confirmed = [r for r in records if r.status == FeedbackStatus.HUMAN_CONFIRMED]
    exportable = approved + confirmed

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in exportable:
            payload = responses.get(r.record_id, {})
            row = {
                "record_id": r.record_id,
                "behavior_id": r.behavior_id,
                "status": r.status.value,
                "has_wrong_response": r.has_wrong_response,
                "has_verified_correct_response": r.has_verified_correct_response,
                "has_verified_preference_pair": r.has_verified_preference_pair,
                "response": payload.get("response"),
                "correct_response": payload.get("correct_response"),
            }
            f.write(json.dumps(row, default=str) + "\n")
    return path
