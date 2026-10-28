"""OpenAI-compatible provider tests (offline — no network calls).

These tests only exercise the fail-closed guards; no HTTP request is made
because the guards raise before any client is constructed.
"""

from __future__ import annotations

import asyncio

import pytest

from agentevalops.config.settings import GenerationConfig, ModelSpec
from agentevalops.errors import ProviderError
from agentevalops.evaluation.prompting import EvalPrompt
from agentevalops.evaluation.providers.openai_compat import OpenAICompatProvider


def _prompt() -> EvalPrompt:
    return EvalPrompt(behavior_id="tool_failure_recovery", frame="FAILURE", instance_id="i1")


def _spec() -> ModelSpec:
    return ModelSpec(id="m", provider_model="openai/deepseek-flash", provider="openai_compat")


def test_provider_requires_api_key() -> None:
    provider = OpenAICompatProvider(api_key=None)
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.generate(_prompt(), _spec(), GenerationConfig()))
    assert exc.value.code == "PROVIDER_UNAVAILABLE"


def test_provider_fail_closed_on_external_traces() -> None:
    # A key is present, but the privacy gate (allow_external_raw_traces) is off
    # by default, so no trace may be sent to an external model.
    provider = OpenAICompatProvider(api_key="sk-dummy")
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.generate(_prompt(), _spec(), GenerationConfig()))
    assert exc.value.code == "EXTERNAL_TRACES_DISABLED"
