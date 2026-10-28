"""Model-based judge backends.

A :class:`TextCompletionBackend` is the minimal contract a model-based judge
(rubric scoring or candidate confirmation) needs: turn a system + user prompt
into text. This keeps grading/confirmation decoupled from any concrete model
provider, and lets offline tests use deterministic fakes.
"""

from __future__ import annotations

import asyncio
import json
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx


class TextCompletionBackend(ABC):
    name: str = "base"
    version: str = "v1"

    @abstractmethod
    async def complete(self, system: str, user: str) -> str:
        """Return raw text for a (system, user) prompt."""


class OpenAICompatBackend(TextCompletionBackend):
    """OpenAI-compatible chat backend for model-based judging.

    Calls any ``/chat/completions`` endpoint (e.g. Zhipu GLM, DeepSeek, OpenAI)
    with a plain system+user prompt and returns the assistant text. Failures
    raise ``ValueError`` so the judge records an ERROR verdict instead of
    crashing the pipeline.
    """

    name = "openai_compat_backend"
    version = "v1"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 60.0,
        extra_body: dict[str, Any] | None = None,
        max_retries: int = 4,
        retry_backoff: float = 2.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.extra_body = extra_body or {}
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.max_tokens = int(self.extra_body.pop("max_tokens", 512))

    async def complete(self, system: str, user: str) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.0,
            "max_tokens": self.max_tokens,
        }
        for key, value in self.extra_body.items():
            payload.setdefault(key, value)

        last_error: ValueError | None = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=payload,
                    )
            except httpx.HTTPError as exc:
                last_error = ValueError(f"judge backend request failed: {exc}")
                if attempt < self.max_retries:
                    await asyncio.sleep(min(self.retry_backoff ** attempt, 30.0))
                    continue
                raise last_error from exc

            if resp.status_code == 200:
                data = resp.json()
                message = (data.get("choices") or [{}])[0].get("message") or {}
                text = message.get("content") or ""
                if not text.strip():
                    raise ValueError("judge backend returned empty content")
                return text

            # Retry transient rate-limit / server errors with backoff.
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                last_error = ValueError(f"judge backend returned {resp.status_code}")
                await asyncio.sleep(min(self.retry_backoff ** attempt, 30.0))
                continue
            raise ValueError(f"judge backend returned {resp.status_code}: {resp.text[:200]}")

        raise last_error or ValueError("judge backend failed")


def extract_json(text: str) -> dict[str, Any]:
    """Best-effort JSON extraction: direct parse, then fenced block, then brace span."""
    text = text.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        try:
            obj = json.loads(fence.group(1))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last > first:
        try:
            obj = json.loads(text[first : last + 1])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    raise ValueError("no JSON object found in model output")
