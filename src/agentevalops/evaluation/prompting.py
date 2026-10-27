"""Decision-point continuation prompt rendering."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agentevalops.schemas.benchmark import BenchmarkInstance, ContextMessage, ToolDefinition

SYSTEM_PROMPT = (
    "You are an AI agent completing a task. Below is the conversation so far. "
    "Produce your next assistant message to continue the task. You may call one or "
    "more of the available tools."
)


class EvalPrompt(BaseModel):
    system: str = SYSTEM_PROMPT
    messages: list[ContextMessage] = Field(default_factory=list)
    tool_definitions: list[ToolDefinition] = Field(default_factory=list)
    behavior_id: str
    frame: str
    cut_metadata: dict[str, Any] = Field(default_factory=dict)
    instance_id: str


def build_prompt(instance: BenchmarkInstance) -> EvalPrompt:
    return EvalPrompt(
        messages=instance.context,
        tool_definitions=instance.tool_definitions,
        behavior_id=instance.behavior_id,
        frame=instance.frame.value,
        cut_metadata=instance.cut_metadata,
        instance_id=instance.instance_id,
    )
