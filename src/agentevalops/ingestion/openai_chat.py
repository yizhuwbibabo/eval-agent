"""Generic OpenAI tool-message trajectory importer.

Reads JSONL where each line is ``{"messages": [...], "tools": [...],
"metadata": {...}}`` with OpenAI chat tool-calling structure (assistant
``tool_calls`` + ``tool`` messages with ``tool_call_id``). This covers
tool-use trajectory datasets such as ``GurkanOz/tool-failure-recovery-trajectories``
and any OpenAI-format agent trace export.

Tool-result content that looks like a failure marker (e.g. ``[SOCKET_HANGUP]``,
or a JSON object with an ``error`` key) is recorded as the event's ``error`` with
``status=ERROR`` so downstream anchors can recall failure decision points.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from agentevalops.ingestion.base import FailedRecord, ImportResult, ImportWarning, TraceImporter
from agentevalops.schemas.trace import EventStatus, Trace, TraceEvent, TraceEventType

# Bracket error markers like [SOCKET_HANGUP] or [REQUEST_TIMEOUT: no response
# after 60s]. Content must start with an uppercase token.
_BRACKET_MARKER = re.compile(r"^\[[A-Z][A-Za-z0-9_ :,.'\-]*\]$")


def detect_tool_error(content: Any) -> str | None:
    """Return an error string if the tool-result content signals a failure.

    Real OpenAI tool-use trajectories signal failure in many ways; this covers
    the ones observed in ``GurkanOz/tool-failure-recovery-trajectories``:

    * bracket error markers (``[SOCKET_HANGUP]``, ``[REQUEST_TIMEOUT: ...]``)
    * JSON payloads with an ``error`` key (``{"error": "...", "code": 429}``)
    * malformed JSON data payloads (``{"data": [1,2,,]}``)
    * JS/language exception strings (``SyntaxError: ...``, ``null``,
      ``response.body is undefined``)
    * parse-fail markers (``%%%%PARSE_FAIL%%%%``)

    Successful results (JSON without an ``error`` key) return ``None``.
    """
    if isinstance(content, dict):
        if content.get("error"):
            return str(content["error"])[:200]
        return None
    if not isinstance(content, str):
        return None
    s = content.strip()
    if not s:
        return None
    if _BRACKET_MARKER.match(s):
        return s
    if "PARSE_FAIL" in s:
        return "PARSE_FAIL"
    if s[0] == "{" and s[-1] == "}":
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            return "MALFORMED_JSON"
        if isinstance(obj, dict) and obj.get("error"):
            return str(obj["error"])[:200]
        return None
    if s == "null":
        return "NULL_RESULT"
    if s.startswith("SyntaxError"):
        return "SYNTAX_ERROR"
    if s == "response.body is undefined":
        return "UNEXPECTED_RESPONSE"
    return None


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    return {"value": raw}


def record_to_trace(record: Any, index: int) -> tuple[Trace, list[ImportWarning]]:
    warnings: list[ImportWarning] = []
    messages = record.get("messages") or [] if isinstance(record, dict) else []
    tools = record.get("tools") or [] if isinstance(record, dict) else []
    metadata = record.get("metadata") or {} if isinstance(record, dict) else {}

    tool_definitions: list[dict[str, Any]] = []
    for t in tools:
        if isinstance(t, dict) and isinstance(t.get("function"), dict):
            fn = t["function"]
            tool_definitions.append(
                {"name": fn.get("name", ""), "description": fn.get("description", ""), "parameters": fn.get("parameters", {})}
            )

    events: list[TraceEvent] = []
    assistant_idx = 0
    for mi, msg in enumerate(messages):
        if not isinstance(msg, dict):
            warnings.append(ImportWarning(code="UNPARSED_MESSAGE", message="message is not an object", record_index=index))
            continue
        role = msg.get("role")
        content = msg.get("content")

        if role == "user":
            events.append(
                TraceEvent(event_id=f"e{mi}", event_type=TraceEventType.USER, role="user", content=content if isinstance(content, str) else None, input_origin="user")
            )
        elif role == "assistant":
            assistant_idx += 1
            turn_id = f"t{assistant_idx}"
            events.append(
                TraceEvent(
                    event_id=f"e{mi}",
                    event_type=TraceEventType.ASSISTANT,
                    role="assistant",
                    turn_id=turn_id,
                    content=content if isinstance(content, str) else None,
                )
            )
            for tci, tc in enumerate(msg.get("tool_calls") or []):
                if not isinstance(tc, dict):
                    warnings.append(ImportWarning(code="UNPARSED_TOOL_CALL", message="tool call is not an object", record_index=index))
                    continue
                fn = tc.get("function") or {}
                call_id = tc.get("id") or f"call{assistant_idx}_{tci}"
                events.append(
                    TraceEvent(
                        event_id=f"e{mi}:tc{tci}",
                        event_type=TraceEventType.TOOL_CALL,
                        role="assistant",
                        turn_id=turn_id,
                        tool_name=fn.get("name", ""),
                        tool_call_id=call_id,
                        tool_arguments=_parse_arguments(fn.get("arguments")),
                    )
                )
        elif role == "tool":
            error = detect_tool_error(content)
            events.append(
                TraceEvent(
                    event_id=f"e{mi}",
                    event_type=TraceEventType.TOOL_RESULT,
                    role="tool",
                    tool_call_id=msg.get("tool_call_id"),
                    tool_result=content,
                    error=error,
                    status=EventStatus.ERROR if error else EventStatus.SUCCESS,
                )
            )
        elif role == "system":
            events.append(TraceEvent(event_id=f"e{mi}", event_type=TraceEventType.SYSTEM, role="system", content=content if isinstance(content, str) else None))
        else:
            warnings.append(ImportWarning(code="UNKNOWN_ROLE", message=f"unknown role {role!r}", record_index=index, unparsed_fields=["role"]))

    trace_metadata = dict(metadata)
    if tool_definitions:
        trace_metadata["tool_definitions"] = tool_definitions

    trace = Trace(
        trace_id=f"openai-chat:{index:06d}",
        source_system=metadata.get("source_system", "openai_chat"),
        dataset_source=str(metadata.get("domain", "openai_chat")),
        metadata=trace_metadata,
        events=events,
    )
    return trace, warnings


class OpenAIChatImporter(TraceImporter):
    name = "openai_chat"

    def import_file(self, path: str | Path) -> ImportResult:
        traces: list[Trace] = []
        warnings: list[ImportWarning] = []
        failed: list[FailedRecord] = []
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError as exc:
                    failed.append(FailedRecord(record_index=i, error=f"invalid JSON: {exc.msg}"))
                    continue
                try:
                    t, w = record_to_trace(rec, i)
                    traces.append(t)
                    warnings.extend(w)
                except Exception as exc:  # noqa: BLE001 - importer boundary
                    failed.append(FailedRecord(record_index=i, error=str(exc)))
        return ImportResult(source_type="openai_chat", traces=traces, warnings=warnings, failed_records=failed)

    def import_string(self, content: str) -> ImportResult:
        traces: list[Trace] = []
        warnings: list[ImportWarning] = []
        failed: list[FailedRecord] = []
        for i, line in enumerate(content.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                failed.append(FailedRecord(record_index=i, error=f"invalid JSON: {exc.msg}"))
                continue
            try:
                t, w = record_to_trace(rec, i)
                traces.append(t)
                warnings.extend(w)
            except Exception as exc:  # noqa: BLE001
                failed.append(FailedRecord(record_index=i, error=str(exc)))
        return ImportResult(source_type="openai_chat", traces=traces, warnings=warnings, failed_records=failed)
