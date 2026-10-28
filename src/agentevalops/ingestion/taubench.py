"""τ-bench (tau-bench) trajectory importer.

τ-bench (https://github.com/sierra-research/tau-bench, Apache-2.0) records
multi-turn tool-agent-user interactions in retail/airline/telecom domains. Each
trajectory is ``{id, domain, user_id, task, messages: [...], reward_info}``
where ``messages`` use the OpenAI tool-calling shape (assistant ``tool_calls``
+ ``tool`` messages) — the same shape ``OpenAIChatImporter`` reads. The task
description and ``reward_info.reward`` are preserved as trace metadata, and the
binary task reward is exposed as a ground-truth label for calibration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentevalops.ingestion.base import FailedRecord, ImportResult, ImportWarning, TraceImporter
from agentevalops.ingestion.openai_chat import record_to_trace
from agentevalops.schemas.trace import Trace


def tau_record_to_trace(record: Any, index: int) -> tuple[Trace, list[ImportWarning]]:
    """Map a τ-bench record into the unified Trace schema."""
    if not isinstance(record, dict):
        raise ValueError("τ-bench record must be an object")

    normalized: dict[str, Any] = {
        "messages": record.get("messages") or [],
        "tools": record.get("tools") or [],
        "metadata": {
            "source_system": "tau-bench",
            "domain": record.get("domain"),
            "task": record.get("task"),
            "user_id": record.get("user_id"),
            "task_id": record.get("task_id"),
            "reward_info": record.get("reward_info"),
        },
    }
    trace, warnings = record_to_trace(normalized, index)
    # τ-bench ground-truth label (task success) for grader calibration.
    reward_info = record.get("reward_info") or {}
    if "reward" in reward_info:
        trace.metadata["ground_truth_label"] = bool(reward_info.get("reward", 0.0) >= 1.0)
    return trace, warnings


class TauBenchImporter(TraceImporter):
    name = "taubench"

    def import_file(self, path: str | Path) -> ImportResult:
        return self._import_lines(Path(path).read_text(encoding="utf-8").splitlines(), source=path)

    def import_string(self, content: str) -> ImportResult:
        return self._import_lines(content.splitlines(), source="<string>")

    def _import_lines(self, lines: list[str], source: Any) -> ImportResult:
        traces: list[Trace] = []
        warnings: list[ImportWarning] = []
        failed: list[FailedRecord] = []
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                failed.append(FailedRecord(record_index=i, error=f"invalid JSON: {exc.msg}"))
                continue
            try:
                t, w = tau_record_to_trace(rec, i)
                traces.append(t)
                warnings.extend(w)
            except Exception as exc:  # noqa: BLE001 - importer boundary
                failed.append(FailedRecord(record_index=i, error=str(exc)))
        return ImportResult(source_type="taubench", traces=traces, warnings=warnings, failed_records=failed)
