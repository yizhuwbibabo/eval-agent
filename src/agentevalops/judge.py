"""Model-based judge backends.

A :class:`TextCompletionBackend` is the minimal contract a model-based judge
(rubric scoring or candidate confirmation) needs: turn a system + user prompt
into text. This keeps grading/confirmation decoupled from any concrete model
provider, and lets offline tests use deterministic fakes.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any


class TextCompletionBackend(ABC):
    name: str = "base"
    version: str = "v1"

    @abstractmethod
    async def complete(self, system: str, user: str) -> str:
        """Return raw text for a (system, user) prompt."""


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
