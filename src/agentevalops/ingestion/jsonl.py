"""Generic JSONL trace importer.

Each line is one trace object following the unified trace schema. A leading
``{"traces": [...]}`` wrapper or a single JSON object is also accepted.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from agentevalops.ingestion.base import FailedRecord, ImportResult, ImportWarning, TraceImporter
from agentevalops.schemas.trace import Trace, TraceEvent


def _coerce_event(raw: dict[str, Any], index: int) -> tuple[TraceEvent | None, list[ImportWarning]]:
    """Build a TraceEvent, coercing stringified JSON where safe."""
    warnings: list[ImportWarning] = []
    raw = dict(raw)
    for field in ("tool_arguments",):
        val = raw.get(field)
        if isinstance(val, str):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, dict):
                    raw[field] = parsed
                else:
                    warnings.append(
                        ImportWarning(
                            code="INVALID_JSON",
                            message="tool_arguments is a string that parses to non-object",
                            field=field,
                            record_index=index,
                        )
                    )
            except json.JSONDecodeError:
                warnings.append(
                    ImportWarning(
                        code="INVALID_JSON",
                        message="tool_arguments string is not valid JSON",
                        field=field,
                        record_index=index,
                    )
                )
                raw[field] = None
    try:
        return TraceEvent(**raw), warnings
    except ValidationError as exc:
        raise exc


class JsonlTraceImporter(TraceImporter):
    name = "jsonl"

    def import_file(self, path: str | Path) -> ImportResult:
        return self.import_string(Path(path).read_text(encoding="utf-8"))

    def import_string(self, content: str) -> ImportResult:
        traces: list[Trace] = []
        warnings: list[ImportWarning] = []
        failed: list[FailedRecord] = []

        # A top-level JSON array or {"traces": [...]} wrapper.
        stripped = content.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                # Fall through to line-based parsing.
                obj = None
            if isinstance(obj, dict) and "traces" in obj:
                raw_traces = obj["traces"]
                for i, raw in enumerate(raw_traces):
                    self._import_one(raw, i, traces, warnings, failed)
                return ImportResult(
                    source_type="jsonl", traces=traces, warnings=warnings, failed_records=failed
                )
            if isinstance(obj, list):
                for i, raw in enumerate(obj):
                    self._import_one(raw, i, traces, warnings, failed)
                return ImportResult(
                    source_type="jsonl", traces=traces, warnings=warnings, failed_records=failed
                )
            if isinstance(obj, dict):
                self._import_one(obj, 0, traces, warnings, failed)
                return ImportResult(
                    source_type="jsonl", traces=traces, warnings=warnings, failed_records=failed
                )

        # Line-based JSONL.
        for i, line in enumerate(content.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                failed.append(
                    FailedRecord(record_index=i, error=f"invalid JSON: {exc.msg}", raw_preview=line[:200])
                )
                continue
            self._import_one(raw, i, traces, warnings, failed)

        return ImportResult(
            source_type="jsonl", traces=traces, warnings=warnings, failed_records=failed
        )

    def _import_one(
        self,
        raw: Any,
        index: int,
        traces: list[Trace],
        warnings: list[ImportWarning],
        failed: list[FailedRecord],
    ) -> None:
        if not isinstance(raw, dict):
            failed.append(FailedRecord(record_index=index, error="record is not an object"))
            return
        events_raw = raw.get("events", [])
        events: list[TraceEvent] = []
        for raw_event in events_raw:
            try:
                event, event_warnings = _coerce_event(raw_event, index)
                if event is not None:
                    events.append(event)
                warnings.extend(event_warnings)
            except ValidationError as exc:
                failed.append(
                    FailedRecord(
                        record_index=index,
                        error=f"event validation failed: {exc.errors()[:3]}",
                        raw_preview=json.dumps(raw_event)[:200],
                    )
                )
        try:
            trace = Trace(**{**raw, "events": events})
        except ValidationError as exc:
            failed.append(
                FailedRecord(
                    record_index=index,
                    error=f"trace validation failed: {exc.errors()[:3]}",
                    raw_preview=json.dumps(raw)[:200],
                )
            )
            return
        traces.append(trace)
