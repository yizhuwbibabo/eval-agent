"""Evaluation runner integration tests."""

from __future__ import annotations

import asyncio

from agentevalops.benchmark.builder import BenchmarkBuilder
from agentevalops.config.settings import ExecutionConfig, GenerationConfig, ModelSpec
from agentevalops.errors import RateLimitError
from agentevalops.evaluation.models import ModelRegistry
from agentevalops.evaluation.providers.base import ModelProvider
from agentevalops.evaluation.providers.mock import compliant
from agentevalops.evaluation.runner import EvalRunner
from agentevalops.persistence import get_store
from agentevalops.schemas.benchmark import BenchmarkDataset
from agentevalops.schemas.evaluation import TrialStatus


def _dataset(registry, traces):
    builder = BenchmarkBuilder(registry)
    instances = []
    for bid in registry.ids():
        instances.extend(builder.build(traces, bid, "b", "v1").dataset.instances)
    return BenchmarkDataset(benchmark_id="b", dataset_version="v1", instances=instances)


def _models() -> list[ModelSpec]:
    return [
        ModelSpec(id="model_a", provider_model="mock/compliant"),
        ModelSpec(id="model_b", provider_model="mock/error_prone"),
    ]


async def test_mock_provider_runs(registry, traces) -> None:
    runner = EvalRunner(ModelRegistry(), ExecutionConfig(concurrency=2), GenerationConfig())
    outcome = await runner.run(_dataset(registry, traces), _models(), "r1", trials_per_instance=1)
    assert outcome.run.status.value == "COMPLETED"
    assert len(outcome.trials) == 8  # 4 instances x 2 models
    assert all(t.status == TrialStatus.COMPLETED for t in outcome.trials)


async def test_model_switch_requires_no_logic_change(registry, traces) -> None:
    runner = EvalRunner(ModelRegistry(), ExecutionConfig(concurrency=2), GenerationConfig())
    single = [ModelSpec(id="model_a", provider_model="mock/compliant")]
    outcome = await runner.run(_dataset(registry, traces), single, "r2", trials_per_instance=1)
    assert {t.model_id for t in outcome.trials} == {"model_a"}


async def test_rate_limit_retry_has_cap(registry, traces) -> None:
    class FlakyProvider(ModelProvider):
        name = "flaky"

        def __init__(self) -> None:
            self.calls = 0

        async def generate(self, prompt, model_spec, generation):
            self.calls += 1
            if self.calls <= 1:
                raise RateLimitError("rate limited")
            return compliant(prompt)

    registry_m = ModelRegistry({"flaky": FlakyProvider()})
    ds = _dataset(registry, traces)
    # limit to one instance for determinism
    ds = BenchmarkDataset(benchmark_id="b", dataset_version="v1", instances=ds.instances[:1])
    runner = EvalRunner(
        registry_m,
        ExecutionConfig(concurrency=1, retry_attempts=2, retry_backoff_base=0.01),
        GenerationConfig(),
    )
    outcome = await runner.run(ds, [ModelSpec(id="m", provider_model="flaky/x", provider="flaky")], "r3", 1)
    assert outcome.trials[0].status == TrialStatus.COMPLETED
    assert outcome.trials[0].retries == 1


async def test_timeout_recorded(registry, traces) -> None:
    class SlowProvider(ModelProvider):
        name = "slow"

        async def generate(self, prompt, model_spec, generation):
            await asyncio.sleep(5)
            return compliant(prompt)

    ds = _dataset(registry, traces)
    ds = BenchmarkDataset(benchmark_id="b", dataset_version="v1", instances=ds.instances[:1])
    runner = EvalRunner(
        ModelRegistry({"slow": SlowProvider()}),
        ExecutionConfig(concurrency=1, timeout_seconds=0.1, retry_attempts=0),
        GenerationConfig(),
    )
    outcome = await runner.run(ds, [ModelSpec(id="m", provider_model="slow/x", provider="slow")], "r4", 1)
    assert outcome.trials[0].status == TrialStatus.FAILED
    assert outcome.trials[0].error_code == "TIMEOUT"


async def test_resume_does_not_rerun_completed(registry, traces, tmp_path) -> None:
    store = get_store(f"sqlite:///{tmp_path}/t.db")
    ds = _dataset(registry, traces)
    runner = EvalRunner(ModelRegistry(), ExecutionConfig(concurrency=2), GenerationConfig(), store)
    await runner.run(ds, _models(), "r5", trials_per_instance=1)
    first_count = len(store.get_trials("r5"))
    outcome2 = await runner.run(ds, _models(), "r5", trials_per_instance=1, resume=True)
    assert len(outcome2.trials) == 0  # all skipped
    assert len(store.get_trials("r5")) == first_count


async def test_config_snapshot_recorded(registry, traces) -> None:
    runner = EvalRunner(ModelRegistry(), ExecutionConfig(concurrency=2), GenerationConfig())
    outcome = await runner.run(_dataset(registry, traces), _models(), "r6", 1, config_snapshot={"a": 1})
    assert outcome.run.config_snapshot == {"a": 1}
