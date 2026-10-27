"""Inspect AI integration test (skipped if Inspect is not installed)."""

from __future__ import annotations

import pytest

inspect_ai = pytest.importorskip("inspect_ai")

from agentevalops.benchmark.builder import BenchmarkBuilder  # noqa: E402


def test_mock_inspect_model_generates(registry, traces) -> None:
    from agentevalops.evaluation.inspect_tasks.task import _instance_ctx, mock_model

    builder = BenchmarkBuilder(registry)
    inst = builder.build(traces, "error_guided_correction", "b", "v1").dataset.instances[0]
    _instance_ctx.set(inst)
    model = mock_model("mock/compliant")
    assert model.api is not None
    import asyncio

    from inspect_ai.model import ChatMessageUser

    out = asyncio.run(model.api.generate([ChatMessageUser(content="hi")], [], "none", None))
    assert out.model == "mock/compliant"
    assert out.choices[0].message.tool_calls


def test_build_task(registry, traces) -> None:
    from agentevalops.evaluation.inspect_tasks.task import build_task

    builder = BenchmarkBuilder(registry)
    instances = []
    for bid in registry.ids():
        instances.extend(builder.build(traces, bid, "b", "v1").dataset.instances)
    task = build_task(instances, model_name="mock/compliant", name="test")
    assert task.name == "test"
    assert task.model is not None
