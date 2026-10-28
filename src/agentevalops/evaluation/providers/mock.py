"""Offline mock model provider.

Three deterministic profiles demonstrate *distinct* model behaviors without any
API key:

* ``compliant`` - applies corrections, inspects logs, verifies edits, asks for
  confirmation.
* ``error_prone`` - repeats failing operations, skips logs, claims completion
  without verification, performs destructive actions without confirmation.
* ``wrong_tool`` - calls a tool that is not in the task's tool definitions.

These are mocks for offline testing; they are never presented as real models.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agentevalops.config.settings import GenerationConfig, ModelSpec
from agentevalops.evaluation.prompting import EvalPrompt
from agentevalops.evaluation.providers.base import ModelProvider
from agentevalops.schemas.evaluation import AssistantTurn, ToolCall, Usage


def _tc(name: str, args: dict[str, Any], call_id: str) -> ToolCall:
    return ToolCall(call_id=call_id, tool_name=name, arguments=args)


def _turn(text: str | None, tool_calls: list[ToolCall]) -> AssistantTurn:
    return AssistantTurn(
        text=text,
        tool_calls=tool_calls,
        finish_reason="tool_calls" if tool_calls else "stop",
        provider_metadata={"provider": "mock"},
        usage=Usage(input_tokens=1, output_tokens=1, total_tokens=2),
    )


def _extract_path(prompt: EvalPrompt) -> str:
    for msg in reversed(prompt.messages):
        if msg.tool_arguments and "path" in msg.tool_arguments:
            return msg.tool_arguments["path"]
    return "parser.py"


def compliant(prompt: EvalPrompt) -> AssistantTurn:
    bid = prompt.behavior_id
    meta = prompt.cut_metadata
    if bid == "error_guided_correction":
        tool = meta.get("tool_name")
        fix = meta.get("suggested_correction")
        if tool and isinstance(fix, dict):
            return _turn("Applying the suggested correction.", [_tc(tool, fix, "m1")])
        return _turn("Applying the correction.", [])
    if bid == "failure_log_inspection":
        insp = (meta.get("inspection_tools") or ["read_logs"])[0]
        return _turn("Inspecting the logs first.", [_tc(insp, meta.get("original_arguments") or {}, "m1")])
    if bid == "post_edit_verification":
        ver = (meta.get("verification_tools") or ["run_tests"])[0]
        return _turn("Verifying the change.", [_tc(ver, {"path": _extract_path(prompt)}, "m1")])
    if bid == "unsafe_action_without_confirmation":
        conf = (meta.get("confirmation_tools") or ["request_confirmation"])[0]
        return _turn("This is destructive; requesting confirmation.", [_tc(conf, {"action": "proceed"}, "m1")])
    if bid == "tool_failure_recovery":
        tool = meta.get("tool_name")
        if isinstance(tool, str):
            return _turn("Retrying the failed call.", [_tc(tool, meta.get("original_arguments") or {}, "m1")])
        return _turn("Retrying.", [])
    return _turn("Done.", [])


def error_prone(prompt: EvalPrompt) -> AssistantTurn:
    bid = prompt.behavior_id
    meta = prompt.cut_metadata
    if bid == "error_guided_correction":
        tool = meta.get("tool_name")
        if not isinstance(tool, str):
            return _turn("Retrying.", [])
        return _turn("Retrying.", [_tc(tool, meta.get("original_arguments") or {}, "m1")])
    if bid == "failure_log_inspection":
        mod = (meta.get("modify_tools") or ["retry_job"])[0]
        return _turn("Retrying the job.", [_tc(mod, meta.get("original_arguments") or {}, "m1")])
    if bid == "post_edit_verification":
        return _turn("Done, the task is complete.", [])
    if bid == "unsafe_action_without_confirmation":
        dest = (meta.get("destructive_tools") or ["delete_production_data"])[0]
        return _turn("Proceeding with deletion.", [_tc(dest, {"table": "orders"}, "m1")])
    if bid == "tool_failure_recovery":
        return _turn("The tool call failed; I cannot complete this task.", [])
    return _turn("Done.", [])


def wrong_tool(prompt: EvalPrompt) -> AssistantTurn:
    bid = prompt.behavior_id
    if bid == "error_guided_correction":
        return _turn("Trying a different approach.", [_tc("run_lint", {"path": "x.py"}, "m1")])
    if bid == "failure_log_inspection":
        return _turn("Restarting the service.", [_tc("restart_service", {"service": "api"}, "m1")])
    if bid == "post_edit_verification":
        return _turn("Done, the task is complete.", [])
    if bid == "unsafe_action_without_confirmation":
        return _turn("Dropping the table.", [_tc("drop_table", {"table": "orders"}, "m1")])
    if bid == "tool_failure_recovery":
        return _turn("Trying a different tool.", [_tc("cancel_event", {"id": "x"}, "m1")])
    return _turn("Done.", [])


Responder = Callable[[EvalPrompt], AssistantTurn]


def default_profiles() -> dict[str, Responder]:
    return {"compliant": compliant, "error_prone": error_prone, "wrong_tool": wrong_tool}


class MockProvider(ModelProvider):
    name = "mock"

    def __init__(self, profiles: dict[str, Responder] | None = None) -> None:
        self.profiles = profiles or default_profiles()

    async def generate(
        self, prompt: EvalPrompt, model_spec: ModelSpec, generation: GenerationConfig
    ) -> AssistantTurn:
        key = model_spec.provider_model.split("/")[-1]
        responder = self.profiles.get(key)
        if responder is None:
            from agentevalops.errors import ProviderError

            raise ProviderError(f"no mock profile for {model_spec.provider_model!r}")
        turn = responder(prompt)
        turn.provider_metadata = {
            "provider": "mock",
            "model": model_spec.provider_model,
            "version": "mock-1.0",
            "profile": key,
        }
        return turn
