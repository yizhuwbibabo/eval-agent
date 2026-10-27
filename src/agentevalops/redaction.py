"""Configurable privacy redaction and secret detection.

Redaction rules are regex-based and named; raw and redacted data are always
handled separately by the callers (importers keep raw traces on disk while
downstream evaluation uses redacted copies).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from agentevalops.schemas.trace import Trace, TraceEvent

_REPLACEMENT = "[REDACTED:{rule}]"


@dataclass(frozen=True)
class RedactionRule:
    name: str
    pattern: str
    replacement: str = _REPLACEMENT
    _compiled: re.Pattern[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_compiled", re.compile(self.pattern))


DEFAULT_RULES: list[RedactionRule] = [
    RedactionRule("api_key", r"(?i)\b(api[_-]?key|apikey|access[_-]?token|auth[_-]?token|secret[_-]?key)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{8,}"),
    RedactionRule("bearer_token", r"(?i)bearer\s+[A-Za-z0-9\-\._~\+\/]+=*"),
    RedactionRule("secret_key", r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{8,}\b"),
    RedactionRule("github_token", r"\b(?:ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{8,}\b"),
    RedactionRule("aws_secret_key", r"\bAKIA[0-9A-Z]{16}\b"),
    RedactionRule("private_path", r"(?:/home/|/Users/|C:\\Users\\)[A-Za-z0-9_\-\.\\/]+"),
    RedactionRule("email", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    RedactionRule("ip_address", r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    RedactionRule("credit_card", r"\b(?:\d[ -]*?){13,16}\b"),
]


@dataclass
class RedactionHit:
    rule: str
    field: str
    event_id: str | None = None
    trace_id: str | None = None


class Redactor:
    """Applies a set of rules to strings and structured trace data."""

    def __init__(self, rules: list[RedactionRule] | None = None) -> None:
        self.rules = rules or DEFAULT_RULES

    def redact_string(self, value: str) -> tuple[str, list[str]]:
        hits: list[str] = []
        out = value
        for rule in self.rules:
            if rule._compiled.search(out):
                hits.append(rule.name)
                out = rule._compiled.sub(rule.replacement.format(rule=rule.name), out)
        return out, hits

    def redact_value(self, value: Any) -> tuple[Any, list[str]]:
        hits: list[str] = []
        if isinstance(value, str):
            return self.redact_string(value)
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            for k, v in value.items():
                out[k], h = self.redact_value(v)
                hits.extend(h)
            return out, hits
        if isinstance(value, list):
            out_list: list[Any] = []
            for v in value:
                rv, h = self.redact_value(v)
                out_list.append(rv)
                hits.extend(h)
            return out_list, hits
        return value, hits

    def scan_event(self, event: TraceEvent) -> list[RedactionHit]:
        hits: list[RedactionHit] = []
        fields: dict[str, Any] = {
            "content": event.content,
            "tool_arguments": event.tool_arguments,
            "tool_result": event.tool_result,
            "error": event.error,
        }
        for field_name, value in fields.items():
            if value is None:
                continue
            _, rule_hits = self.redact_value(value)
            for rule in rule_hits:
                hits.append(RedactionHit(rule=rule, field=field_name, event_id=event.event_id))
        return hits

    def redact_trace(self, trace: Trace) -> tuple[Trace, list[RedactionHit]]:
        hits: list[RedactionHit] = []
        new_events: list[TraceEvent] = []
        for event in trace.events:
            data = event.model_dump()
            for field_name in ("content", "tool_arguments", "tool_result", "error"):
                value = data.get(field_name)
                if value is None:
                    continue
                new_value, rule_hits = self.redact_value(value)
                data[field_name] = new_value
                for rule in rule_hits:
                    hits.append(
                        RedactionHit(
                            rule=rule,
                            field=field_name,
                            event_id=event.event_id,
                            trace_id=trace.trace_id,
                        )
                    )
            new_events.append(TraceEvent(**data))
        return trace.model_copy(update={"events": new_events}), hits


def default_redactor() -> Redactor:
    return Redactor()
