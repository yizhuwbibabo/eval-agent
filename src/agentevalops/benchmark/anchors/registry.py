"""Anchor registry and dispatch."""

from __future__ import annotations

from agentevalops.benchmark.anchors.argument_check import ArgumentCheckAnchor
from agentevalops.benchmark.anchors.base import Anchor
from agentevalops.benchmark.anchors.error_instruction import ErrorInstructionAnchor
from agentevalops.benchmark.anchors.event_sequence import EventSequenceAnchor
from agentevalops.benchmark.anchors.status_check import StatusCheckAnchor
from agentevalops.benchmark.anchors.tool_error import ToolErrorAnchor

_ANCHORS: dict[str, Anchor] = {
    a.name: a
    for a in [
        ToolErrorAnchor(),
        ErrorInstructionAnchor(),
        StatusCheckAnchor(),
        EventSequenceAnchor(),
        ArgumentCheckAnchor(),
    ]
}


def get_anchor(anchor_type: str) -> Anchor:
    if anchor_type not in _ANCHORS:
        raise KeyError(f"unknown anchor type {anchor_type!r}; available: {sorted(_ANCHORS)}")
    return _ANCHORS[anchor_type]


def available_anchors() -> list[str]:
    return sorted(_ANCHORS)
