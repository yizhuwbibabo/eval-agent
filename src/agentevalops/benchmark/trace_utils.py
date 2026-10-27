"""Trace manipulation helpers shared by anchors, the cutter and the confirmer."""

from __future__ import annotations

from agentevalops.schemas.trace import Trace, TraceEvent, TraceEventType


def find_call(trace: Trace, tool_call_id: str | None) -> TraceEvent | None:
    if tool_call_id is None:
        return None
    for e in trace.events:
        if e.event_type == TraceEventType.TOOL_CALL and e.tool_call_id == tool_call_id:
            return e
    return None


def events_by_turn(trace: Trace) -> dict[str, list[TraceEvent]]:
    groups: dict[str, list[TraceEvent]] = {}
    for e in trace.events:
        key = e.turn_id or f"__no_turn_{e.event_id}"
        groups.setdefault(key, []).append(e)
    return groups


def next_turn_after(trace: Trace, event_id: str) -> list[TraceEvent]:
    """Events of the first assistant turn that starts after ``event_id``."""
    idx = _index_of(trace, event_id)
    if idx is None:
        return []
    # Skip events that share the cut event's turn (continuation of the same turn).
    cut_turn = trace.events[idx].turn_id
    start = idx + 1
    while start < len(trace.events) and trace.events[start].turn_id == cut_turn:
        start += 1
    if start >= len(trace.events):
        return []
    turn = trace.events[start].turn_id
    return [e for e in trace.events[start:] if e.turn_id == turn]


def turn_of(trace: Trace, event_id: str) -> list[TraceEvent]:
    idx = _index_of(trace, event_id)
    if idx is None:
        return []
    turn = trace.events[idx].turn_id
    if turn is None:
        return [trace.events[idx]]
    return [e for e in trace.events if e.turn_id == turn]


def _index_of(trace: Trace, event_id: str) -> int | None:
    for i, e in enumerate(trace.events):
        if e.event_id == event_id:
            return i
    return None


def is_terminal_assistant(trace: Trace, index: int) -> bool:
    """True if the assistant event at ``index`` has no tool call in its turn."""
    e = trace.events[index]
    if e.turn_id is None:
        return True
    for nxt in trace.events[index + 1 :]:
        if nxt.turn_id != e.turn_id:
            return True
        if nxt.event_type == TraceEventType.TOOL_CALL:
            return False
    return True
