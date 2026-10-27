"""Ingestion integration tests."""

from __future__ import annotations

from agentevalops.ingestion.jsonl import JsonlTraceImporter
from agentevalops.ingestion.registry import import_file


def test_jsonl_import_valid(tmp_path) -> None:
    path = tmp_path / "traces.jsonl"
    path.write_text(
        '{"trace_id":"t1","source_system":"x","dataset_source":"synthetic",'
        '"events":[{"event_id":"e1","event_type":"user","content":"hi"}]}\n'
    )
    result = import_file(path)
    assert len(result.traces) == 1
    assert result.traces[0].trace_id == "t1"
    assert not result.failed_records


def test_jsonl_import_invalid_json_recorded(tmp_path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text("{not valid json}\n")
    result = import_file(path)
    assert not result.traces
    assert len(result.failed_records) == 1


def test_jsonl_import_missing_field_rejected(tmp_path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text('{"trace_id":"t1","source_system":"x","dataset_source":"synthetic","events":[{"event_type":"user"}]}\n')
    result = import_file(path)
    # event missing event_id -> validation failure recorded
    assert result.failed_records or result.traces == []


def test_jsonl_import_wrapped_array(tmp_path) -> None:
    importer = JsonlTraceImporter()
    content = (
        '{"traces":[{"trace_id":"t1","source_system":"x","dataset_source":"synthetic","events":[]},'
        '{"trace_id":"t2","source_system":"x","dataset_source":"synthetic","events":[]}]}'
    )
    result = importer.import_string(content)
    assert len(result.traces) == 2


def test_inspect_importer_from_log(tmp_path) -> None:
    import json

    log = {
        "version": 1,
        "results": {
            "samples": [
                {
                    "id": "s1",
                    "input": "hello",
                    "messages": [
                        {"role": "user", "content": "hello"},
                        {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "function": "run_query", "arguments": {"q": "x"}}]},
                        {"role": "tool", "tool_call_id": "c1", "content": '{"rows": 1}'},
                    ],
                }
            ]
        },
    }
    path = tmp_path / "log.eval"
    path.write_text(json.dumps(log))
    result = import_file(path, "inspect")
    assert len(result.traces) == 1
    trace = result.traces[0]
    assert trace.source_system == "inspect_ai"
    assert any(e.event_type.value == "tool_call" for e in trace.events)
    assert any(e.event_type.value == "tool_result" for e in trace.events)
