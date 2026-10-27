"""Evaluation layer."""

from agentevalops.evaluation.dataset import DatasetManager, load_dataset_for_run
from agentevalops.evaluation.models import ModelRegistry, default_registry
from agentevalops.evaluation.prompting import EvalPrompt, build_prompt
from agentevalops.evaluation.runner import EvalRunner, RunOutcome

__all__ = [
    "DatasetManager",
    "EvalPrompt",
    "EvalRunner",
    "ModelRegistry",
    "RunOutcome",
    "build_prompt",
    "default_registry",
    "load_dataset_for_run",
]
