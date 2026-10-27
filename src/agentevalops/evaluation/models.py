"""Model registry: maps a model spec's ``provider`` to a provider instance."""

from __future__ import annotations

from agentevalops.config.settings import ModelSpec
from agentevalops.evaluation.providers.base import ModelProvider
from agentevalops.evaluation.providers.mock import MockProvider
from agentevalops.evaluation.providers.openai_compat import OpenAICompatProvider


class ModelRegistry:
    def __init__(self, providers: dict[str, ModelProvider] | None = None) -> None:
        self._providers = providers or {
            "mock": MockProvider(),
            "openai_compat": OpenAICompatProvider(),
        }

    def get_provider(self, model_spec: ModelSpec) -> ModelProvider:
        if model_spec.provider not in self._providers:
            raise KeyError(
                f"no provider for {model_spec.provider!r}; available: {sorted(self._providers)}"
            )
        return self._providers[model_spec.provider]

    def register(self, name: str, provider: ModelProvider) -> None:
        self._providers[name] = provider


def default_registry() -> ModelRegistry:
    return ModelRegistry()
