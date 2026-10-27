"""Versioned, unified trace schema.

The trace schema is the canonical intermediate representation for every
importer. It deliberately keeps raw provenance (``source_system``,
``dataset_source``, ``schema_version``) and never throws away fields that a
downstream importer cannot fully parse - such fields are recorded in
``metadata["unparsed"]`` with an explicit data-loss note.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

TRACE_SCHEMA_VERSION = "1.0"


class TraceEventType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    SYSTEM = "system"
    HARNESS = "harness"
    ERROR = "error"


class EventRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"
    HARNESS = "harness"


class EventStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TraceEvent(BaseModel):
    """A single event in a trace.

    One assistant turn may contain multiple tool calls. Events belonging to the
    same turn share a ``turn_id``; a tool result links back to its call via
    ``tool_call_id``. This allows the cutter to reconstruct multi-tool-call
    turns and to handle out-of-order tool results.
    """

    event_id: str
    event_type: TraceEventType
    timestamp: datetime | None = None
    role: str | None = None
    # Distinguishes user messages from harness-injected messages.
    input_origin: str | None = None
    turn_id: str | None = None
    content: str | None = None
    tool_name: str | None = None
    tool_call_id: str | None = None
    tool_arguments: dict[str, Any] | None = None
    tool_result: Any = None
    error: str | None = None
    status: EventStatus | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Trace(BaseModel):
    """A full agent trace."""

    trace_id: str
    session_id: str | None = None
    source_system: str
    source_model: str | None = None
    dataset_source: str
    timestamp: datetime | None = None
    schema_version: str = TRACE_SCHEMA_VERSION
    metadata: dict[str, Any] = Field(default_factory=dict)
    events: list[TraceEvent] = Field(default_factory=list)

    def event_by_id(self, event_id: str) -> TraceEvent | None:
        for e in self.events:
            if e.event_id == event_id:
                return e
        return None

    def ordered_events(self) -> list[TraceEvent]:
        """Events sorted by timestamp when available, else by original order."""
        stamped = [(i, e) for i, e in enumerate(self.events)]
        return [e for _, e in sorted(stamped, key=lambda t: (t[1].timestamp or datetime.min, t[0]))]
