"""Leak checking for cut decision points.

Guarantees the source agent's continuation (the target response) never appears
in the context handed to the model under test.
"""

from __future__ import annotations

from agentevalops.schemas.benchmark import ContextMessage
from agentevalops.schemas.trace import TraceEvent


def check_leak(context: list[ContextMessage], target_events: list[TraceEvent]) -> list[str]:
    """Return human-readable leak descriptions (empty list means no leak)."""
    leaks: list[str] = []
    target_ids = {e.event_id for e in target_events if e.event_id}
    target_texts = {e.content for e in target_events if e.content}
    target_call_ids = {e.tool_call_id for e in target_events if e.tool_call_id}

    for msg in context:
        if msg.event_id and msg.event_id in target_ids:
            leaks.append(f"target event {msg.event_id} leaked into context")
        if msg.content and msg.content in target_texts:
            leaks.append(f"target content leaked via event {msg.event_id}")
        if msg.tool_call_id and msg.tool_call_id in target_call_ids:
            leaks.append(f"target tool call {msg.tool_call_id} leaked into context")
    return leaks


def assert_no_leak(context: list[ContextMessage], target_events: list[TraceEvent]) -> None:
    leaks = check_leak(context, target_events)
    if leaks:
        raise AssertionError("source continuation leaked into context: " + "; ".join(leaks))
