"""Deterministic graders.

Program-verifiable conditions: tool-name validity, tool-argument schema
validity, and the structurally checkable rubric criteria. Each rule produces an
explicit hit with rule id, evidence and severity; nothing is keyword-matched
into a semantic verdict.
"""

from __future__ import annotations

from agentevalops.grading.criteria import CRITERION_SEVERITY, evaluate_criteria
from agentevalops.schemas.benchmark import BenchmarkInstance
from agentevalops.schemas.evaluation import AssistantTurn
from agentevalops.schemas.grading import DeterministicHit


def _tool_name_validity(instance: BenchmarkInstance, turn: AssistantTurn) -> DeterministicHit:
    defined = {t.name for t in instance.tool_definitions}
    unknown = [c.tool_name for c in turn.tool_calls if c.tool_name not in defined]
    return DeterministicHit(
        rule_id="tool_name_validity",
        matched=bool(unknown),
        evidence_event_ids=[],
        message=f"tool calls reference undefined tools: {unknown}" if unknown else "all tool names valid",
        severity="critical" if unknown else "info",
        metadata={"unknown_tools": unknown},
    )


def _tool_argument_required_fields(instance: BenchmarkInstance, turn: AssistantTurn) -> DeterministicHit:
    schema: dict[str, dict] = {t.name: t.parameters for t in instance.tool_definitions}
    violations: list[str] = []
    for c in turn.tool_calls:
        params = schema.get(c.tool_name)
        if not params:
            continue
        required = params.get("required") or []
        missing = [r for r in required if r not in (c.arguments or {})]
        if missing:
            violations.append(f"{c.tool_name}: missing {missing}")
    return DeterministicHit(
        rule_id="tool_argument_required_fields",
        matched=bool(violations),
        evidence_event_ids=[],
        message="; ".join(violations) if violations else "tool arguments satisfy required fields",
        severity="critical" if violations else "info",
        metadata={"violations": violations},
    )


def evaluate_deterministic(instance: BenchmarkInstance, turn: AssistantTurn) -> list[DeterministicHit]:
    hits: list[DeterministicHit] = [
        _tool_name_validity(instance, turn),
        _tool_argument_required_fields(instance, turn),
    ]
    cr = evaluate_criteria(instance, turn)
    for criterion_id, met in cr.criteria.items():
        severity = CRITERION_SEVERITY.get(criterion_id, "high")
        evidence = cr.evidence.get(criterion_id) or []
        hits.append(
            DeterministicHit(
                rule_id=criterion_id,
                matched=not met,
                evidence_event_ids=[e.event_id for e in evidence if e.event_id],
                message=(
                    f"criterion {criterion_id!r} satisfied"
                    if met
                    else f"criterion {criterion_id!r} violated"
                ),
                severity="info" if met else severity,
                metadata={"criterion_id": criterion_id},
            )
        )
    return hits


def hard_violations(hits: list[DeterministicHit]) -> list[DeterministicHit]:
    return [h for h in hits if h.matched and h.severity == "critical"]
