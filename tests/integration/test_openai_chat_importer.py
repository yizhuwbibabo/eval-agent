"""OpenAI tool-message importer tests against real recovery-trajectory data.

The fixture (``tests/fixtures/traces/recovery_sample.jsonl``) is a 5-record
sample of ``GurkanOz/tool-failure-recovery-trajectories`` covering tool_success
and recovery records with the diverse failure markers seen in the wild.
"""

from __future__ import annotations

from agentevalops.benchmark.builder import BenchmarkBuilder
from agentevalops.ingestion.openai_chat import OpenAIChatImporter, detect_tool_error
from agentevalops.schemas.trace import EventStatus, TraceEventType


def _import_sample(repo_root):
    return OpenAIChatImporter().import_file(repo_root / "tests" / "fixtures" / "traces" / "recovery_sample.jsonl")


def test_import_recovery_sample(repo_root) -> None:
    result = _import_sample(repo_root)
    assert result.source_type == "openai_chat"
    assert len(result.traces) == 5
    assert not result.failed_records


def test_detect_tool_error_variants() -> None:
    assert detect_tool_error("[SOCKET_HANGUP]") == "[SOCKET_HANGUP]"
    assert detect_tool_error("[REQUEST_TIMEOUT: no response after 60s]") == "[REQUEST_TIMEOUT: no response after 60s]"
    assert detect_tool_error('{"error": "Quota exhausted for this API key", "code": 429}') == "Quota exhausted for this API key"
    assert detect_tool_error('{"data": [1,2,,]}') == "MALFORMED_JSON"
    assert detect_tool_error("null") == "NULL_RESULT"
    assert detect_tool_error("SyntaxError: unexpected token at position 41") == "SYNTAX_ERROR"
    assert detect_tool_error("response.body is undefined") == "UNEXPECTED_RESPONSE"
    assert detect_tool_error("%%%%PARSE_FAIL%%%%") == "PARSE_FAIL"
    # successful payloads are not errors
    assert detect_tool_error('{"status": "sent", "message_id": "msg_88213"}') is None
    assert detect_tool_error('{"results": [1, 2]}') is None
    assert detect_tool_error("") is None
    assert detect_tool_error(None) is None
    assert detect_tool_error({"error": "boom"}) == "boom"
    assert detect_tool_error({"ok": True}) is None


def test_failure_tool_results_marked_error(repo_root) -> None:
    result = _import_sample(repo_root)
    errors = [
        (e.tool_name, e.error)
        for t in result.traces
        for e in t.events
        if e.event_type == TraceEventType.TOOL_RESULT and e.status == EventStatus.ERROR
    ]
    assert len(errors) == 3
    detected = {err for _, err in errors}
    assert detected == {"[SOCKET_HANGUP]", "NULL_RESULT", "[REQUEST_TIMEOUT: no response after 60s]"}


def test_build_tool_failure_recovery_benchmark(repo_root, registry) -> None:
    result = _import_sample(repo_root)
    build = BenchmarkBuilder(registry).build(
        result.traces, "tool_failure_recovery", "recovery", "v1", source_type="real"
    )
    assert build.stats.candidate_count == 3
    assert build.stats.confirmed_count == 3
    assert build.stats.valid_instance_count == 3
    for inst in build.dataset.instances:
        assert inst.cut_metadata.get("tool_name")
        assert inst.cut_metadata.get("error_event_id")
        assert inst.source_type == "real"
