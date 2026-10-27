"""Inspect AI integration for decision-point evaluation.

Wraps the benchmark dataset as an Inspect ``Task`` with a custom solver, scorer
and a mock model provider. This is an *optional* integration: the native runner
remains the fully-offline path, and this module reuses the same grading layer.

The API here is written against the installed Inspect AI version (0.3.x) and
verified at import time; it is guarded so the rest of the package works without
Inspect installed.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from agentevalops.evaluation.prompting import EvalPrompt
from agentevalops.evaluation.providers.mock import default_profiles
from agentevalops.grading.deterministic import evaluate_deterministic
from agentevalops.grading.hybrid import merge
from agentevalops.grading.llm_judge import MockRubricJudge
from agentevalops.schemas.benchmark import BenchmarkInstance, ToolDefinition
from agentevalops.schemas.evaluation import AssistantTurn, ToolCall

_instance_ctx: ContextVar[BenchmarkInstance | None] = ContextVar("inspect_instance", default=None)


def _to_inspect_messages(context: list) -> list:
    from inspect_ai.model import (
        ChatMessageAssistant,
        ChatMessageSystem,
        ChatMessageTool,
        ChatMessageUser,
    )

    messages: list[Any] = []
    for m in context:
        if m.role == "tool" and m.tool_call_id:
            messages.append(
                ChatMessageTool(content=_render_tool_result(m.tool_result, m.error), tool_call_id=m.tool_call_id, function=m.tool_name or "")
            )
        elif m.role == "assistant" and m.tool_arguments is not None and m.tool_call_id:
            messages.append(
                ChatMessageAssistant(
                    content=m.content or "",
                    tool_calls=[{"id": m.tool_call_id, "function": m.tool_name or "", "arguments": m.tool_arguments or {}}],
                )
            )
        elif m.role == "user":
            messages.append(ChatMessageUser(content=m.content or ""))
        elif m.role == "system":
            messages.append(ChatMessageSystem(content=m.content or ""))
        else:
            messages.append(ChatMessageUser(content=m.content or ""))
    return messages


def _render_tool_result(tool_result: Any, error: str | None) -> str:
    if error:
        return f"error: {error}"
    if tool_result is None:
        return ""
    if isinstance(tool_result, str):
        return tool_result
    import json

    return json.dumps(tool_result)


def _to_inspect_tools(tool_definitions: list[ToolDefinition]) -> list:
    """Build Inspect ``Tool`` objects.

    Inspect derives tool schemas from typed function signatures; for the mock
    decision-point path we register each tool name/description with a generic
    ``**kwargs`` callable (tools are never actually executed - the model only
    proposes tool calls).
    """
    from inspect_ai.tool import tool

    tools: list[Any] = []
    for td in tool_definitions:
        def _dummy(**kwargs: Any) -> str:
            """Placeholder tool (never executed in decision-point eval)."""
            return ""

        _dummy.__name__ = td.name
        _dummy.__doc__ = td.description
        tools.append(tool(name=td.name)(_dummy))
    return tools


def decision_point_solver():
    """Install the cut context as messages and generate once."""
    from inspect_ai.solver import Generate, TaskState, solver

    @solver
    def _solver():
        async def solve(state: TaskState, generate: Generate) -> TaskState:
            raw = state.metadata.get("instance")
            instance = BenchmarkInstance.model_validate(raw) if raw else None
            if instance is not None:
                state.messages = _to_inspect_messages(instance.context)
                state.tools = _to_inspect_tools(instance.tool_definitions)
                _instance_ctx.set(instance)
                # Single-step generation: decision-point continuation evaluates
                # one assistant turn and does NOT execute tool calls.
                from inspect_ai.model import get_model

                model = get_model(str(state.model))
                state.output = await model.generate(state.messages, state.tools, "auto")
            else:
                await generate(state)
            return state

        return solve

    return _solver()


def decision_point_scorer(judge: MockRubricJudge | None = None, pass_threshold: float = 4.0):
    """Score the model's continuation with the shared grading layer."""
    from inspect_ai.scorer import Score, Target, scorer

    judge = judge or MockRubricJudge()

    @scorer(metrics=[])
    def _scorer():
        async def score(state, target: Target) -> Score:
            raw = state.metadata.get("instance")
            instance = BenchmarkInstance.model_validate(raw) if raw else None
            turn = _extract_turn(state)
            if instance is None or turn is None:
                return Score(value="I", explanation="could not reconstruct instance or response")
            rubric = _rubric_for(instance)
            verdict = await judge.grade(instance, turn, rubric)
            hits = evaluate_deterministic(instance, turn)
            hybrid = merge(hits, verdict, "hybrid", pass_threshold)
            value: Any = "I"
            if hybrid.passed is not None:
                value = "C" if hybrid.passed else "I"
            return Score(
                value=value,
                explanation=verdict.reason,
                metadata={
                    "score": hybrid.final_score,
                    "passed": hybrid.passed,
                    "violated_criteria": verdict.violated_criteria,
                    "overridden_by": hybrid.overridden_by,
                },
            )

        return score

    return _scorer()


def _rubric_for(instance: BenchmarkInstance):
    from agentevalops.benchmark.registry import BehaviorRegistry

    registry = BehaviorRegistry.from_dir("configs/behaviors")
    return registry.get(instance.behavior_id).rubric


def _extract_turn(state) -> AssistantTurn | None:
    output = state.output
    if output is None or not getattr(output, "choices", None):
        return None
    message = output.choices[-1].message
    tool_calls = [
        ToolCall(
            call_id=_tc_field(tc, "id", f"call_{i}"),
            tool_name=_tc_field(tc, "function", "") or _tc_field(tc, "name", ""),
            arguments=_tc_field(tc, "arguments", {}),
        )
        for i, tc in enumerate(getattr(message, "tool_calls", None) or [])
    ]
    return AssistantTurn(
        text=getattr(message, "content", None),
        tool_calls=tool_calls,
        finish_reason=getattr(output.choices[-1], "stop_reason", None),
    )


def _tc_field(tc: Any, name: str, default: Any) -> Any:
    if isinstance(tc, dict):
        return tc.get(name, default)
    return getattr(tc, name, default)


try:
    from inspect_ai.model import GenerateConfig, Model, ModelAPI, modelapi

    _HAS_INSPECT = True
except Exception:  # pragma: no cover - inspected optional
    _HAS_INSPECT = False
    Model = None  # type: ignore[assignment]
    ModelAPI = object  # type: ignore[assignment]
    GenerateConfig = None  # type: ignore[assignment]

    def modelapi(name: str):  # type: ignore[misc]
        def deco(cls):
            return cls

        return deco


if _HAS_INSPECT:

    @modelapi("mock")
    class MockModelAPI(ModelAPI):
        def __init__(self, model_name: str = "mock/compliant", **kwargs: Any) -> None:
            super().__init__(model_name=model_name, **kwargs)
            self._profile = model_name.split("/")[-1]

        async def generate(self, input, tools, tool_choice, config):
            from inspect_ai.model import ChatCompletionChoice, ChatMessageAssistant, ModelOutput

            instance = _instance_ctx.get()
            prompt = EvalPrompt(
                messages=instance.context if instance else [],
                tool_definitions=instance.tool_definitions if instance else [],
                behavior_id=instance.behavior_id if instance else "",
                frame=instance.frame.value if instance else "",
                cut_metadata=instance.cut_metadata if instance else {},
                instance_id=instance.instance_id if instance else "",
            )
            responder = default_profiles().get(self._profile)
            turn = responder(prompt) if responder else AssistantTurn(text="")
            msg = ChatMessageAssistant(
                content=turn.text,
                tool_calls=[
                    {"id": c.call_id, "function": c.tool_name, "arguments": c.arguments}
                    for c in turn.tool_calls
                ],
            )
            return ModelOutput(
                model=self.model_name,
                choices=[ChatCompletionChoice(message=msg, stop_reason=turn.finish_reason or "stop")],
            )

        def is_auth_failure(self, ex: Exception) -> bool:
            return False

        def should_retry(self, ex: Exception) -> bool:
            return False

        def count_tokens(self, input: Any, tools: Any = None) -> int:
            return 0


def mock_model(model_name: str = "mock/compliant", **kwargs: Any):
    """Return an Inspect ``Model`` wrapping the mock model API."""
    if not _HAS_INSPECT:
        raise ImportError("inspect_ai is not installed; cannot build an Inspect mock model")
    return Model(api=MockModelAPI(model_name=model_name, **kwargs), config=GenerateConfig())


class MockInspectModel:
    """Compatibility alias: builds an Inspect ``Model`` for the mock provider."""

    def __new__(cls, model_name: str = "mock/compliant", **kwargs: Any):
        return mock_model(model_name=model_name, **kwargs)


def build_task(dataset: list[BenchmarkInstance], model_name: str = "mock/compliant", name: str = "agent_behavior"):
    """Build an Inspect ``Task`` from benchmark instances."""
    from inspect_ai import Task
    from inspect_ai.dataset import MemoryDataset, Sample

    samples = [
        Sample(
            input=f"decision point: {i.instance_id}",
            target="",
            id=i.instance_id,
            metadata={"instance": i.model_dump(mode="json")},
        )
        for i in dataset
    ]
    return Task(
        dataset=MemoryDataset(samples=samples, name=name),
        solver=decision_point_solver(),
        scorer=decision_point_scorer(),
        model=MockInspectModel(model_name=model_name),
        name=name,
    )
