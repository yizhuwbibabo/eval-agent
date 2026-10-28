"""OpenAI-compatible model provider (optional, requires an API key).

Wraps any OpenAI-compatible ``/chat/completions`` endpoint. Without an API key
this provider raises ``ProviderError`` - it is never used to fabricate offline
results.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from agentevalops.config.settings import GenerationConfig, ModelSpec, get_settings
from agentevalops.errors import ProviderError, ProviderUnavailableError
from agentevalops.evaluation.prompting import EvalPrompt
from agentevalops.evaluation.providers.base import ModelProvider
from agentevalops.schemas.evaluation import AssistantTurn, ToolCall, Usage


class OpenAICompatProvider(ModelProvider):
    name = "openai_compat"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.timeout = timeout

    async def generate(
        self, prompt: EvalPrompt, model_spec: ModelSpec, generation: GenerationConfig
    ) -> AssistantTurn:
        if not self.api_key:
            raise ProviderError(
                "OPENAI_API_KEY is not set; cannot call a real model",
                code="PROVIDER_UNAVAILABLE",
            )
        if not get_settings().allow_external_raw_traces:
            raise ProviderError(
                "sending traces to an external model is disabled by default; "
                "set AGENTEVALOPS_ALLOW_EXTERNAL_RAW_TRACES=true to opt in",
                code="EXTERNAL_TRACES_DISABLED",
            )
        messages = self._render_messages(prompt)
        tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in prompt.tool_definitions
        ]
        payload: dict[str, Any] = {
            "model": model_spec.provider_model.split("/")[-1],
            "messages": messages,
            "temperature": generation.temperature,
            "max_tokens": generation.max_output_tokens,
        }
        # Provider-specific extras (e.g. DeepSeek thinking mode) come from the
        # model spec config; reserved keys are never overridden by config.
        for key, value in (model_spec.config or {}).items():
            payload.setdefault(key, value)
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"provider request failed: {exc}") from exc

        if resp.status_code == 429:
            from agentevalops.errors import RateLimitError

            raise RateLimitError("rate limited by provider")
        if resp.status_code != 200:
            raise ProviderError(f"provider returned {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        tool_calls = [
            ToolCall(
                call_id=(tc.get("id") or f"call_{i}"),
                tool_name=tc.get("function", {}).get("name", ""),
                arguments=json.loads(tc.get("function", {}).get("arguments") or "{}"),
            )
            for i, tc in enumerate(message.get("tool_calls") or [])
        ]
        usage = data.get("usage") or {}
        return AssistantTurn(
            text=message.get("content"),
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason"),
            provider_metadata={"provider": "openai_compat", "model": payload["model"]},
            usage=Usage(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            ),
        )

    def _render_messages(self, prompt: EvalPrompt) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": prompt.system}]
        for m in prompt.messages:
            if m.role == "tool" and m.tool_call_id:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": m.tool_call_id,
                        "content": (
                            m.tool_result
                            if isinstance(m.tool_result, str)
                            else json.dumps(m.tool_result)
                            if m.tool_result is not None
                            else (m.error or "")
                        ),
                    }
                )
            elif m.role == "assistant" and m.tool_arguments is not None and m.tool_call_id:
                messages.append(
                    {
                        "role": "assistant",
                        "content": m.content or "",
                        "tool_calls": [
                            {
                                "id": m.tool_call_id,
                                "type": "function",
                                "function": {"name": m.tool_name or "", "arguments": json.dumps(m.tool_arguments)},
                            }
                        ],
                    }
                )
            else:
                messages.append({"role": m.role if m.role in ("user", "assistant", "system") else "user", "content": m.content or ""})
        return messages
