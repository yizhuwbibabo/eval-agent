"""Importer for Inspect AI evaluation logs (``.eval`` files).

Maps each Inspect sample into one trace. The importer is defensive about the
exact log layout because Inspect's JSON schema changes across versions; any
field that cannot be mapped is reported as unparsed rather than dropped.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentevalops.ingestion.base import FailedRecord, ImportResult, ImportWarning, TraceImporter
from agentevalops.schemas.trace import EventStatus, Trace, TraceEvent, TraceEventType


class InspectLogImporter(TraceImporter):
    name = "inspect"

    def import_file(self, path: str | Path) -> ImportResult:
        return self.import_string(Path(path).read_text(encoding="utf-8"))

    def import_string(self, content: str) -> ImportResult:
        try:
            log = json.loads(content)
        except json.JSONDecodeError as exc:
            return ImportResult(
                source_type="inspect",
                failed_records=[FailedRecord(error=f"invalid JSON: {exc.msg}")],
            )

        samples: list[Any] = []
        if isinstance(log, dict):
            results = log.get("results") or {}
            if isinstance(results, dict) and isinstance(results.get("samples"), list):
                samples = results["samples"]
            elif isinstance(log.get("samples"), list):
                samples = log["samples"]
            elif isinstance(log.get("eval"), dict) and isinstance(log["eval"].get("samples"), list):
                samples = log["eval"]["samples"]

        traces: list[Trace] = []
        warnings: list[ImportWarning] = []
        failed: list[FailedRecord] = []

        for i, sample in enumerate(samples):
            try:
                trace, sample_warnings = self._sample_to_trace(sample, i)
                traces.append(trace)
                warnings.extend(sample_warnings)
            except Exception as exc:  # noqa: BLE001 - importer boundary records, never swallows silently
                failed.append(FailedRecord(record_index=i, error=f"sample conversion failed: {exc}"))

        return ImportResult(
            source_type="inspect",
            traces=traces,
            warnings=warnings,
            failed_records=failed,
            metadata={"log_version": log.get("version") if isinstance(log, dict) else None},
        )

    def _sample_to_trace(self, sample: Any, index: int) -> tuple[Trace, list[ImportWarning]]:
        warnings: list[ImportWarning] = []
        if not isinstance(sample, dict):
            raise ValueError("sample is not an object")

        sample_id = str(sample.get("id") or f"inspect_sample_{index}")
        messages = sample.get("messages") or []
        events: list[TraceEvent] = []
        turn_counter = 0

        for mi, msg in enumerate(messages):
            if not isinstance(msg, dict):
                warnings.append(
                    ImportWarning(code="UNPARSED_MESSAGE", message="message is not an object", record_index=index)
                )
                continue
            role = msg.get("role")
            content = msg.get("content")
            if isinstance(content, list):
                # Content parts (text/image/...) are flattened to text.
                text_parts = [p.get("text", "") for p in content if isinstance(p, dict)]
                content = "\n".join(t for t in text_parts if t)
                warnings.append(
                    ImportWarning(
                        code="CONTENT_FLATTENED",
                        message="multipart content flattened to text",
                        record_index=index,
                    )
                )
            if content is not None and not isinstance(content, str):
                content = json.dumps(content)

            if role == "assistant":
                turn_counter += 1
                turn_id = f"{sample_id}:{turn_counter}"
                events.append(
                    TraceEvent(
                        event_id=f"{sample_id}:e{mi}",
                        event_type=TraceEventType.ASSISTANT,
                        role="assistant",
                        turn_id=turn_id,
                        content=content,
                    )
                )
                for tc in msg.get("tool_calls") or []:
                    if not isinstance(tc, dict):
                        warnings.append(
                            ImportWarning(code="UNPARSED_TOOL_CALL", message="tool call is not an object", record_index=index)
                        )
                        continue
                    events.append(
                        TraceEvent(
                            event_id=f"{sample_id}:e{mi}:tc{tc.get('id')}",
                            event_type=TraceEventType.TOOL_CALL,
                            role="assistant",
                            turn_id=turn_id,
                            tool_name=tc.get("function") or tc.get("name"),
                            tool_call_id=tc.get("id"),
                            tool_arguments=tc.get("arguments") if isinstance(tc.get("arguments"), dict) else None,
                        )
                    )
            elif role == "tool":
                events.append(
                    TraceEvent(
                        event_id=f"{sample_id}:e{mi}",
                        event_type=TraceEventType.TOOL_RESULT,
                        role="tool",
                        tool_call_id=msg.get("tool_call_id") or msg.get("id"),
                        tool_result=content,
                        error=msg.get("error"),
                        status=EventStatus.ERROR if msg.get("error") else EventStatus.SUCCESS,
                    )
                )
            elif role == "user":
                events.append(
                    TraceEvent(
                        event_id=f"{sample_id}:e{mi}",
                        event_type=TraceEventType.USER,
                        role="user",
                        content=content,
                    )
                )
            elif role == "system":
                events.append(
                    TraceEvent(
                        event_id=f"{sample_id}:e{mi}",
                        event_type=TraceEventType.SYSTEM,
                        role="system",
                        content=content,
                    )
                )
            else:
                warnings.append(
                    ImportWarning(
                        code="UNKNOWN_ROLE",
                        message=f"unknown message role {role!r}",
                        record_index=index,
                    )
                )

        metadata = dict(sample.get("metadata") or {})
        metadata["_inspect_scores"] = sample.get("scores")
        metadata["_inspect_input"] = sample.get("input")

        trace = Trace(
            trace_id=sample_id,
            source_system="inspect_ai",
            source_model=(sample.get("model") if isinstance(sample.get("model"), str) else None),
            dataset_source=sample.get("dataset") if isinstance(sample.get("dataset"), str) else "inspect",
            metadata=metadata,
            events=events,
        )
        return trace, warnings
