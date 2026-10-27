"""Schema validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentevalops.config.settings import EvalConfig, ModelSpec
from agentevalops.schemas.diagnosis import FailureCategory
from agentevalops.schemas.evaluation import AssistantTurn, ToolCall
from agentevalops.schemas.trace import Trace, TraceEvent, TraceEventType


def test_trace_roundtrip() -> None:
    trace = Trace(
        trace_id="t1",
        source_system="x",
        dataset_source="synthetic",
        events=[TraceEvent(event_id="e1", event_type=TraceEventType.USER, content="hi")],
    )
    assert trace.trace_id == "t1"
    assert trace.schema_version == "1.0"
    assert trace.event_by_id("e1") is not None
    assert trace.event_by_id("missing") is None


def test_trace_rejects_invalid_event_type() -> None:
    with pytest.raises(ValidationError):
        TraceEvent(event_id="e1", event_type="not_a_type")  # type: ignore[arg-type]


def test_assistant_turn_supports_multiple_tool_calls() -> None:
    turn = AssistantTurn(
        text="calling tools",
        tool_calls=[
            ToolCall(call_id="c1", tool_name="a", arguments={"x": 1}),
            ToolCall(call_id="c2", tool_name="b", arguments={}),
        ],
    )
    assert len(turn.tool_calls) == 2
    assert turn.tool_calls[0].tool_name == "a"


def test_failure_category_root_leaf() -> None:
    c = FailureCategory.MODEL_BEHAVIOR_ERROR_RECOVERY_FAILURE
    assert c.root == "MODEL_BEHAVIOR"
    assert c.leaf == "ERROR_RECOVERY_FAILURE"


def test_eval_config_requires_unique_models() -> None:
    with pytest.raises(ValidationError):
        EvalConfig.model_validate(
            {
                "evaluation": {"dataset": "d"},
                "models": [
                    {"id": "a", "provider_model": "mock/a"},
                    {"id": "a", "provider_model": "mock/b"},
                ],
            }
        )


def test_eval_config_rejects_empty_models() -> None:
    with pytest.raises(ValidationError):
        EvalConfig.model_validate({"evaluation": {"dataset": "d"}, "models": []})


def test_model_spec_default_provider() -> None:
    m = ModelSpec(id="a", provider_model="mock/a")
    assert m.provider == "mock"
