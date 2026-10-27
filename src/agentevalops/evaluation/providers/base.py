"""Model provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from agentevalops.config.settings import GenerationConfig, ModelSpec
from agentevalops.evaluation.prompting import EvalPrompt
from agentevalops.schemas.evaluation import AssistantTurn


class ModelProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def generate(
        self, prompt: EvalPrompt, model_spec: ModelSpec, generation: GenerationConfig
    ) -> AssistantTurn:
        """Produce the model's next assistant turn for a decision point."""
