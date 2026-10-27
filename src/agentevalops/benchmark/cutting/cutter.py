"""Decision-point cutter (ACTION / FAILURE / CLAIM).

Carves a decision point out of a trace into a model-ready context while keeping
the source agent's continuation strictly out of the context. The continuation
is returned as ``target_event_ids`` for audit and leak checking only.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agentevalops.benchmark.trace_utils import next_turn_after
from agentevalops.schemas.behavior import BehaviorFrame, BehaviorSpecification
from agentevalops.schemas.benchmark import Candidate, ContextMessage, ToolDefinition
from agentevalops.schemas.trace import Trace, TraceEvent


class CutResult(BaseModel):
    context: list[ContextMessage] = Field(default_factory=list)
    cut_metadata: dict[str, Any] = Field(default_factory=dict)
    target_event_ids: list[str] = Field(default_factory=list)
    tool_definitions: list[ToolDefinition] = Field(default_factory=list)


def _to_context_message(event: TraceEvent) -> ContextMessage:
    role = event.role or {
        "user": "user",
        "assistant": "assistant",
        "tool_call": "assistant",
        "tool_result": "tool",
        "system": "system",
        "harness": "system",
        "error": "tool",
    }.get(event.event_type.value, "system")
    return ContextMessage(
        role=role,
        content=event.content,
        tool_name=event.tool_name,
        tool_call_id=event.tool_call_id,
        tool_arguments=event.tool_arguments,
        tool_result=event.tool_result,
        error=event.error,
        event_id=event.event_id,
    )


def _tool_definitions(trace: Trace, behavior: BehaviorSpecification) -> list[ToolDefinition]:
    raw = trace.metadata.get("tool_definitions") or behavior.metadata.get("tool_definitions") or []
    out: list[ToolDefinition] = []
    for item in raw:
        if isinstance(item, ToolDefinition):
            out.append(item)
        elif isinstance(item, dict) and item.get("name"):
            out.append(
                ToolDefinition(
                    name=item["name"],
                    description=item.get("description", ""),
                    parameters=item.get("parameters", {}),
                )
            )
    return out


def _turn_span(events: list[TraceEvent], idx: int) -> tuple[int, int]:
    """Return (start, end) inclusive indices of the turn containing ``idx``."""
    turn_id = events[idx].turn_id
    if turn_id is None:
        return idx, idx
    start = idx
    while start > 0 and events[start - 1].turn_id == turn_id:
        start -= 1
    end = idx
    while end < len(events) - 1 and events[end + 1].turn_id == turn_id:
        end += 1
    return start, end


def cut(trace: Trace, behavior: BehaviorSpecification, candidate: Candidate) -> CutResult:
    frame = behavior.behavior_frame
    mode = behavior.cut_contract.mode
    context_events = behavior.cut_contract.context_events

    idx = next(
        (i for i, e in enumerate(trace.events) if e.event_id == candidate.cut_event_id), None
    )
    if idx is None:
        raise ValueError(f"cut event {candidate.cut_event_id} not found in trace {trace.trace_id}")

    events = trace.events

    if frame == BehaviorFrame.FAILURE:
        # Keep the observed failure and its history; drop the source's next turn.
        context = events[: idx + 1]
        target = next_turn_after(trace, candidate.cut_event_id)
    elif frame == BehaviorFrame.ACTION:
        # Keep context before the target action turn; drop the action turn.
        turn_start, turn_end = _turn_span(events, idx)
        context = events[:turn_start]
        target = events[turn_start : turn_end + 1]
    elif frame == BehaviorFrame.CLAIM:
        # Keep the work and its results; drop the source's claim turn.
        turn_start, turn_end = _turn_span(events, idx)
        context = events[:turn_start]
        target = events[turn_start : turn_end + 1]
    else:  # pragma: no cover - enum is exhaustive
        raise ValueError(f"unsupported frame {frame}")

    # Trim to a bounded context while always retaining the last event.
    if len(context) > context_events:
        context = context[-context_events:]

    context_messages = [_to_context_message(e) for e in context]

    cut_metadata: dict[str, Any] = dict(candidate.metadata)
    cut_metadata["frame"] = frame.value
    cut_metadata["cut_mode"] = mode.value
    cut_metadata["cut_event_id"] = candidate.cut_event_id
    cut_metadata["source_trace_id"] = trace.trace_id

    return CutResult(
        context=context_messages,
        cut_metadata=cut_metadata,
        target_event_ids=[e.event_id for e in target],
        tool_definitions=_tool_definitions(trace, behavior),
    )
