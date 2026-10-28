"""Application and evaluation configuration.

Two layers of configuration exist on purpose:

* :class:`Settings` - process-level settings (database URL, artifact root,
  logging) loaded from environment variables with an ``AGENTEVALOPS_`` prefix.
* :class:`EvalConfig` - per-run evaluation configuration (models, generation,
  execution, grading) loaded from a YAML file such as ``configs/development.yaml``.

Keeping them separate means the model under test is never hard-coded in
evaluation business logic, and secrets stay out of committed YAML.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-level settings loaded from environment / ``.env``."""

    model_config = SettingsConfigDict(
        env_prefix="AGENTEVALOPS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "agentevalops"
    environment: Literal["development", "test", "production"] = "development"

    database_url: str = "sqlite:///./.agentevalops/agentevalops.db"
    artifact_root: str = "reports"
    benchmark_root: str = "datasets"

    log_level: str = "INFO"
    log_json: bool = False

    # Privacy gate: sending unredacted traces to external LLMs is disabled by
    # default. This is deliberately separate from the redaction rules.
    allow_external_raw_traces: bool = False
    # Optional append-only audit log path for external model calls.
    audit_log_path: str | None = None

    def ensure_dirs(self) -> None:
        Path(self.artifact_root).mkdir(parents=True, exist_ok=True)
        Path(self.benchmark_root).mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# --------------------------------------------------------------------------- #
# Evaluation configuration (loaded from YAML)
# --------------------------------------------------------------------------- #


class ModelSpec(BaseModel):
    """A model under test. ``provider`` selects the executor backend."""

    id: str
    provider_model: str
    provider: str = "mock"  # mock | openai_compat | inspect
    config: dict[str, Any] = Field(default_factory=dict)


class GenerationConfig(BaseModel):
    temperature: float = 0.0
    max_output_tokens: int = 4096
    seed: int | None = None


class ExecutionConfig(BaseModel):
    concurrency: int = 4
    timeout_seconds: float = 120.0
    retry_attempts: int = 3
    retry_backoff_base: float = 2.0
    # Only infrastructure errors are retried - never model behavior errors.
    retry_on_codes: list[str] = Field(
        default_factory=lambda: ["TIMEOUT", "RATE_LIMIT", "PROVIDER_UNAVAILABLE"]
    )


class GradingConfig(BaseModel):
    strategy: str = "hybrid"  # deterministic | llm | hybrid
    pass_threshold: float = 4.0
    judge: str = "mock"  # mock | llm
    judge_version: str = "v1"
    # LLM judge backend (used when judge == "llm"). The API key is read from
    # JUDGE_API_KEY in the environment and never stored in the config.
    judge_model: str | None = None
    judge_base_url: str | None = None
    judge_config: dict[str, Any] = Field(default_factory=dict)
    # Concurrency for judge calls during scoring (kept low to respect
    # rate limits; independent of model-under-test concurrency).
    concurrency: int = 4


class EvaluationConfig(BaseModel):
    dataset: str
    dataset_version: str = "v1"
    dataset_path: str | None = None  # explicit path to instances JSONL
    mode: str = "decision_point"
    trials_per_instance: int = 3


class EvalConfig(BaseModel):
    evaluation: EvaluationConfig
    models: list[ModelSpec]
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    grading: GradingConfig = Field(default_factory=GradingConfig)

    @field_validator("models")
    @classmethod
    def _non_empty_unique_models(cls, v: list[ModelSpec]) -> list[ModelSpec]:
        if not v:
            raise ValueError("at least one model must be configured")
        ids = [m.id for m in v]
        if len(ids) != len(set(ids)):
            raise ValueError("model ids must be unique")
        return v


def load_eval_config(path: str | Path) -> EvalConfig:
    """Load an evaluation config from YAML."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"evaluation config {path} must be a YAML mapping")
    return EvalConfig.model_validate(raw)
