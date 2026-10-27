"""LLM-based candidate confirmation.

Uses a text-completion backend to judge whether the candidate decision point
actually exhibits the target behavior. The output is parsed and schema-
validated; model timeouts, JSON errors and scoring failures are reported as
``ERROR`` - never treated as "the behavior is absent".
"""

from __future__ import annotations

import json

from pydantic import ValidationError

from agentevalops.benchmark.confirmation.base import Confirmer
from agentevalops.judge import TextCompletionBackend, extract_json
from agentevalops.schemas.behavior import BehaviorSpecification
from agentevalops.schemas.benchmark import (
    Candidate,
    ConfirmationResult,
    ConfirmationStatus,
)
from agentevalops.schemas.trace import Trace


class LLMConfirmer(Confirmer):
    name = "llm_confirmer"

    def __init__(self, backend: TextCompletionBackend, version: str = "v1") -> None:
        self.backend = backend
        self.version = version

    async def aconfirm(
        self, trace: Trace, behavior: BehaviorSpecification, candidate: Candidate
    ) -> ConfirmationResult:
        system = (
            "You confirm whether a candidate decision point in an agent trace "
            "exhibits a target behavior. Output JSON only."
        )
        user = self._build_prompt(trace, behavior, candidate)
        try:
            text = await self.backend.complete(system, user)
            data = extract_json(text)
            result = ConfirmationResult.model_validate(data)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            return ConfirmationResult(
                candidate_id=candidate.candidate_id,
                is_valid=False,
                target_behavior_observed=False,
                context_sufficient=False,
                decision_already_made=False,
                evidence_event_ids=[],
                reason=f"confirmation judge failed: {exc}",
                status=ConfirmationStatus.ERROR,
                judge_id=self.name,
                judge_version=self.version,
            )
        return result

    def _build_prompt(
        self, trace: Trace, behavior: BehaviorSpecification, candidate: Candidate
    ) -> str:
        window = self._context_window(trace, candidate)
        schema_hint = (
            '{"is_valid": bool, "target_behavior_observed": bool, '
            '"context_sufficient": bool, "decision_already_made": bool, '
            '"evidence_event_ids": [str], "reason": str, "status": '
            '"confirmed|rejected|insufficient_evidence|unsupported|error"}'
        )
        return (
            f"Behavior: {behavior.name}\n"
            f"Description: {behavior.description}\n"
            f"Candidate cut event: {candidate.cut_event_id}\n"
            f"Anchor evidence: {candidate.evidence_event_ids}\n\n"
            f"Trace context (event_id | type | content/tool):\n{window}\n\n"
            f"Does the source agent's continuation exhibit the target behavior? "
            f"Return JSON matching: {schema_hint}"
        )

    def _context_window(self, trace: Trace, candidate: Candidate, limit: int = 12) -> str:
        events = trace.events
        idx = next((i for i, e in enumerate(events) if e.event_id == candidate.cut_event_id), len(events))
        lines = []
        for e in events[max(0, idx - limit) : idx + 2]:
            detail = e.content or e.tool_name or e.error or json.dumps(e.tool_result)[:200] or ""
            lines.append(f"- {e.event_id} | {e.event_type.value} | {detail}")
        return "\n".join(lines)
