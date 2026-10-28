"""τ-bench importer tests (offline, synthetic τ-bench-shaped records)."""

from __future__ import annotations

import json

from agentevalops.ingestion.taubench import TauBenchImporter, tau_record_to_trace


def _record() -> dict:
    return {
        "id": "traj_0",
        "domain": "retail",
        "user_id": "user_0",
        "task_id": "0",
        "task": "You want to refund an order.",
        "messages": [
            {"role": "user", "content": "I want a refund."},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "get_order", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "{\"order\": \"123\"}"},
        ],
        "reward_info": {"reward": 1.0},
    }


def test_tau_record_to_trace() -> None:
    trace, warnings = tau_record_to_trace(_record(), 0)
    assert trace.source_system == "tau-bench"
    assert trace.metadata["domain"] == "retail"
    assert trace.metadata["task"] == "You want to refund an order."
    assert trace.metadata["ground_truth_label"] is True
    assert not warnings


def test_tau_importer_jsonl() -> None:
    importer = TauBenchImporter()
    content = json.dumps(_record()) + "\n" + json.dumps(_record()) + "\n"
    result = importer.import_string(content)
    assert len(result.traces) == 2
    assert all(t.source_system == "tau-bench" for t in result.traces)
    assert not result.failed_records
