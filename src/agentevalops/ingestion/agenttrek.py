"""AgentTrek importer.

AgentTrek (https://huggingface.co/datasets/xlangai/AgentTrek, Apache-2.0) is a
large JSON array of records ``{"messages": [{"role", "content"}, ...]}``. Roles
are ``system`` / ``user`` / ``assistant``. Browser actions are embedded in
assistant content as ``<action> fn(args) </action>`` and the following ``user``
message carries the browser observation (the tool result).

The importer converts each record into a unified :class:`Trace`: each assistant
turn becomes an ``ASSISTANT`` event plus one ``TOOL_CALL`` event, and the
following observation becomes a ``TOOL_RESULT`` event linked by ``tool_call_id``.
The action text is parsed with ``ast.literal_eval`` (literals only - no code
execution from trace content).
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from agentevalops.ingestion.base import FailedRecord, ImportResult, ImportWarning, TraceImporter
from agentevalops.schemas.trace import Trace, TraceEvent, TraceEventType

ACTION_RE = re.compile(r"<action>\s*([A-Za-z_][A-Za-z0-9_]*)\s*\((.*?)\)\s*</action>", re.DOTALL)
SOURCE_URL = "https://huggingface.co/datasets/xlangai/AgentTrek"


def iter_json_array(path: str | Path, chunk_size: int = 1 << 20) -> Iterator[Any]:
    """Stream top-level objects from a JSON array (handles multi-GB files)."""
    decoder = json.JSONDecoder()
    buf = ""
    started = False
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            buf += chunk.decode("utf-8", "replace")
            if not started:
                s = buf.lstrip(" \t\r\n")
                if s.startswith("["):
                    buf = s[1:]
                started = True
            while True:
                s = buf.lstrip(" \t\r\n,")
                if not s or s[0] == "]":
                    break
                try:
                    obj, end = decoder.raw_decode(s)
                except json.JSONDecodeError:
                    break  # incomplete object; read more
                yield obj
                buf = s[end:]
        s = buf.lstrip(" \t\r\n,")
        if s and not s.startswith("]"):
            try:
                obj, _ = decoder.raw_decode(s)
                yield obj
            except json.JSONDecodeError:
                pass


def parse_action(content: str | None) -> tuple[str, dict[str, Any]] | None:
    """Extract ``(fn, args)`` from an ``<action> ... </action>`` block."""
    m = ACTION_RE.search(content or "")
    if not m:
        return None
    fn = m.group(1)
    raw_args = m.group(2).strip()
    if not raw_args:
        return fn, {}
    try:
        parsed = ast.literal_eval(raw_args)
    except (ValueError, SyntaxError):
        return fn, {"raw": raw_args}
    if isinstance(parsed, (list, tuple)):
        return fn, {"args": list(parsed)}
    return fn, {"arg": parsed}


def strip_action(content: str | None) -> str:
    return ACTION_RE.sub("", content or "").strip()


def record_to_trace(
    record: Any, index: int, source_model: str | None = None
) -> tuple[Trace, list[ImportWarning]]:
    warnings: list[ImportWarning] = []
    messages = record.get("messages") or [] if isinstance(record, dict) else []
    events: list[TraceEvent] = []
    assistant_idx = 0
    last_call_id: str | None = None
    user_seen = False

    for mi, msg in enumerate(messages):
        if not isinstance(msg, dict):
            warnings.append(
                ImportWarning(code="UNPARSED_MESSAGE", message="message is not an object", record_index=index)
            )
            continue
        role = msg.get("role")
        content = msg.get("content")
        if content is not None and not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)

        if role == "system":
            events.append(
                TraceEvent(event_id=f"e{mi}", event_type=TraceEventType.SYSTEM, role="system", content=content)
            )
        elif role == "user":
            if not user_seen:
                user_seen = True
                events.append(
                    TraceEvent(event_id=f"e{mi}", event_type=TraceEventType.USER, role="user", content=content, input_origin="user")
                )
            else:
                events.append(
                    TraceEvent(
                        event_id=f"e{mi}",
                        event_type=TraceEventType.TOOL_RESULT,
                        role="tool",
                        tool_call_id=last_call_id,
                        tool_result=content,
                    )
                )
        elif role == "assistant":
            assistant_idx += 1
            turn_id = f"t{assistant_idx}"
            parsed = parse_action(content)
            text = strip_action(content)
            events.append(
                TraceEvent(
                    event_id=f"e{mi}",
                    event_type=TraceEventType.ASSISTANT,
                    role="assistant",
                    turn_id=turn_id,
                    content=text or None,
                )
            )
            if parsed is not None:
                fn, args = parsed
                call_id = f"call{assistant_idx}"
                last_call_id = call_id
                events.append(
                    TraceEvent(
                        event_id=f"e{mi}:call",
                        event_type=TraceEventType.TOOL_CALL,
                        role="assistant",
                        turn_id=turn_id,
                        tool_name=fn,
                        tool_call_id=call_id,
                        tool_arguments=args,
                    )
                )
            else:
                last_call_id = None
        else:
            warnings.append(
                ImportWarning(
                    code="UNKNOWN_ROLE",
                    message=f"unknown message role {role!r}",
                    record_index=index,
                    unparsed_fields=["role"],
                )
            )

    trace = Trace(
        trace_id=f"agenttrek:{index:06d}",
        source_system="agenttrek",
        source_model=source_model,
        dataset_source="agenttrek",
        metadata={
            "origin": "synthesized via guiding replay from web tutorials (not raw production traces)",
            "source_url": SOURCE_URL,
            "record_index": index,
        },
        events=events,
    )
    return trace, warnings


class AgentTrekImporter(TraceImporter):
    name = "agenttrek"

    def import_file(self, path: str | Path, max_traces: int | None = None) -> ImportResult:
        traces: list[Trace] = []
        warnings: list[ImportWarning] = []
        failed: list[FailedRecord] = []
        for i, rec in enumerate(iter_json_array(path)):
            if max_traces is not None and i >= max_traces:
                break
            try:
                t, w = record_to_trace(rec, i)
                traces.append(t)
                warnings.extend(w)
            except Exception as exc:  # noqa: BLE001 - importer boundary records, never swallowed silently
                failed.append(FailedRecord(record_index=i, error=str(exc)))
        return ImportResult(source_type="agenttrek", traces=traces, warnings=warnings, failed_records=failed)

    def import_string(self, content: str) -> ImportResult:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            return ImportResult(source_type="agenttrek", failed_records=[FailedRecord(error=f"invalid JSON: {exc.msg}")])
        records = data if isinstance(data, list) else [data]
        traces: list[Trace] = []
        warnings: list[ImportWarning] = []
        failed: list[FailedRecord] = []
        for i, rec in enumerate(records):
            try:
                t, w = record_to_trace(rec, i)
                traces.append(t)
                warnings.extend(w)
            except Exception as exc:  # noqa: BLE001
                failed.append(FailedRecord(record_index=i, error=str(exc)))
        return ImportResult(source_type="agenttrek", traces=traces, warnings=warnings, failed_records=failed)
