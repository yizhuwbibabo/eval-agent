"""AgentTrek importer tests against real AgentTrek records.

The fixture (``tests/fixtures/traces/agenttrek_sample.json``) is a 3-record
sample of ``xlangai/AgentTrek`` (Apache-2.0). AgentTrek records are *step-level*:
each record is exactly ``system`` + ``user`` + ``assistant``, where the
assistant content embeds a ``<action> fn(args) </action>`` block. There is no
multi-turn tool-result loop in this format, so the importer maps each record to
a single-turn trace rather than fabricating results.
"""

from __future__ import annotations

from agentevalops.ingestion.agenttrek import AgentTrekImporter, parse_action
from agentevalops.schemas.trace import TraceEventType


def _import_sample(repo_root):
    return AgentTrekImporter().import_file(repo_root / "tests" / "fixtures" / "traces" / "agenttrek_sample.json")


def test_parse_action_single_arg() -> None:
    assert parse_action('<action> click("submit") </action>') == ("click", {"arg": "submit"})


def test_parse_action_positional_args() -> None:
    assert parse_action("<action> scroll(0, 200) </action>") == ("scroll", {"args": [0, 200]})


def test_parse_action_no_action() -> None:
    assert parse_action("no action here") is None
    assert parse_action(None) is None


def test_import_agenttrek_sample(repo_root) -> None:
    result = _import_sample(repo_root)
    assert result.source_type == "agenttrek"
    assert len(result.traces) == 3
    assert not result.failed_records


def test_agenttrek_maps_action_to_tool_call(repo_root) -> None:
    result = _import_sample(repo_root)
    for trace in result.traces:
        event_types = [e.event_type for e in trace.events]
        assert TraceEventType.SYSTEM in event_types
        assert TraceEventType.USER in event_types
        assert TraceEventType.ASSISTANT in event_types
        calls = [e for e in trace.events if e.event_type == TraceEventType.TOOL_CALL]
        assert len(calls) == 1
        assert calls[0].tool_name
        assert calls[0].tool_call_id == "call1"
        # AgentTrek is step-level: no observation follows the action.
        assert not any(e.event_type == TraceEventType.TOOL_RESULT for e in trace.events)
