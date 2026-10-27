"""Lightweight in-process span recording.

A minimal tracer-compatible interface so that key pipeline stages can be
instrumented today, with a path to a full OpenTelemetry SDK later. Private
prompts and tool outputs are never attached to spans.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Span:
    name: str
    started_at: float
    ended_at: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float | None:
        if self.ended_at is None:
            return None
        return (self.ended_at - self.started_at) * 1000.0


class Tracer:
    def __init__(self) -> None:
        self.spans: list[Span] = []

    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[Span]:
        s = Span(name=name, started_at=time.monotonic(), attributes=attributes)
        self.spans.append(s)
        try:
            yield s
        finally:
            s.ended_at = time.monotonic()


_current: ContextVar[Tracer | None] = ContextVar("agentevalops_tracer", default=None)


def get_tracer() -> Tracer:
    tracer = _current.get()
    if tracer is None:
        tracer = Tracer()
        _current.set(tracer)
    return tracer
