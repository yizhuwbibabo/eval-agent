"""Async evaluation runner with concurrency, timeout, retry and resume.

Distinguishes infrastructure errors (retryable) from model behavior and data
errors (never retried). Completed trials are checkpointed so a resumed run does
not re-execute already-succeeded samples.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from agentevalops.config.settings import ExecutionConfig, GenerationConfig, ModelSpec
from agentevalops.errors import (
    AgentEvalOpsError,
    ProviderError,
    UnsupportedModelCapability,
)
from agentevalops.evaluation.models import ModelRegistry
from agentevalops.evaluation.prompting import build_prompt
from agentevalops.logging_setup import get_logger
from agentevalops.schemas.benchmark import BenchmarkDataset, BenchmarkInstance
from agentevalops.schemas.evaluation import (
    AssistantTurn,
    EvalRun,
    RunStatus,
    TrialResult,
    TrialStatus,
)

log = get_logger("agentevalops.evaluation.runner")


class RunOutcome:
    def __init__(self, run: EvalRun, trials: list[TrialResult]) -> None:
        self.run = run
        self.trials = trials


class EvalRunner:
    def __init__(
        self,
        registry: ModelRegistry,
        execution: ExecutionConfig,
        generation: GenerationConfig,
        store: Any | None = None,
    ) -> None:
        self.registry = registry
        self.execution = execution
        self.generation = generation
        self.store = store

    async def run(
        self,
        dataset: BenchmarkDataset,
        models: list[ModelSpec],
        run_id: str,
        trials_per_instance: int = 1,
        config_snapshot: dict[str, Any] | None = None,
        resume: bool = False,
    ) -> RunOutcome:
        run = EvalRun(
            run_id=run_id,
            benchmark_id=dataset.benchmark_id,
            dataset_version=dataset.dataset_version,
            status=RunStatus.RUNNING,
            models=[m.id for m in models],
            config_snapshot=config_snapshot or {},
            created_at=datetime.now(timezone.utc),
        )
        if self.store is not None:
            self.store.save_run(run)

        specs = self._trial_specs(dataset, models, run_id, trials_per_instance)
        completed_ids: set[str] = set()
        if resume and self.store is not None:
            completed_ids = self.store.completed_trial_ids(run_id)

        sem = asyncio.Semaphore(max(1, self.execution.concurrency))
        results: list[TrialResult] = []
        failures = 0

        async def run_one(instance: BenchmarkInstance, model: ModelSpec, trial_id: str) -> None:
            nonlocal failures
            if trial_id in completed_ids:
                return
            async with sem:
                trial = await self._run_trial(instance, model, trial_id, run_id)
            results.append(trial)
            if self.store is not None:
                self.store.save_trial(trial)
            if trial.status in (TrialStatus.FAILED, TrialStatus.UNSUPPORTED):
                failures += 1

        tasks = [run_one(inst, model, tid) for (inst, model, tid) in specs]
        try:
            await asyncio.gather(*tasks)
            run.status = RunStatus.COMPLETED
        except asyncio.CancelledError:
            run.status = RunStatus.CANCELLED
            raise
        except Exception:  # noqa: BLE001 - recorded on the run, never swallowed
            run.status = RunStatus.FAILED
            log.exception("evaluation run failed", extra={"run_id": run_id})

        run.completed_at = datetime.now(timezone.utc)
        if self.store is not None:
            self.store.save_run(run)
        return RunOutcome(run, results)

    def _trial_specs(
        self,
        dataset: BenchmarkDataset,
        models: list[ModelSpec],
        run_id: str,
        trials_per_instance: int,
    ) -> list[tuple[BenchmarkInstance, ModelSpec, str]]:
        specs: list[tuple[BenchmarkInstance, ModelSpec, str]] = []
        for inst in dataset.instances:
            for model in models:
                for t in range(trials_per_instance):
                    tid = f"{run_id}::{model.id}::{inst.instance_id}::{t}"
                    specs.append((inst, model, tid))
        return specs

    async def _run_trial(
        self, instance: BenchmarkInstance, model: ModelSpec, trial_id: str, run_id: str
    ) -> TrialResult:
        provider = self.registry.get_provider(model)
        prompt = build_prompt(instance)
        attempt = 0
        start = time.monotonic()
        while True:
            try:
                turn: AssistantTurn = await asyncio.wait_for(
                    provider.generate(prompt, model, self.generation),
                    timeout=self.execution.timeout_seconds,
                )
                return TrialResult(
                    trial_id=trial_id,
                    run_id=run_id,
                    instance_id=instance.instance_id,
                    model_id=model.id,
                    behavior_id=instance.behavior_id,
                    status=TrialStatus.COMPLETED,
                    response=turn,
                    latency_ms=(time.monotonic() - start) * 1000,
                    usage=turn.usage,
                    retries=attempt,
                )
            except asyncio.TimeoutError as exc:
                next_attempt = self._maybe_retry("TIMEOUT", str(exc), attempt, trial_id)
                if next_attempt is None:
                    return self._failed(trial_id, run_id, instance, model, "TIMEOUT", "timed out", start)
                attempt = next_attempt
            except UnsupportedModelCapability as exc:
                return self._unsupported(trial_id, run_id, instance, model, exc)
            except ProviderError as exc:
                if exc.code in self.execution.retry_on_codes:
                    next_attempt = self._maybe_retry(exc.code, exc.message, attempt, trial_id)
                    if next_attempt is None:
                        return self._failed(trial_id, run_id, instance, model, exc.code, exc.message, start)
                    attempt = next_attempt
                else:
                    return self._failed(trial_id, run_id, instance, model, exc.code, exc.message, start)
            except AgentEvalOpsError as exc:
                return self._failed(trial_id, run_id, instance, model, exc.code, exc.message, start)
            except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
                return self._failed(trial_id, run_id, instance, model, "UNEXPECTED", str(exc), start)

    def _maybe_retry(self, code: str, message: str, attempt: int, trial_id: str) -> int | None:
        if attempt >= self.execution.retry_attempts:
            return None
        next_attempt = attempt + 1
        delay = self.execution.retry_backoff_base ** attempt
        log.warning(
            "retrying trial after infrastructure error",
            extra={"trial_id": trial_id, "code": code, "attempt": next_attempt, "delay_s": delay},
        )
        # Synchronous sleep is acceptable for the runner's backoff; callers may
        # prefer an injectable sleeper in tests.
        time.sleep(min(delay, 30.0))
        return next_attempt

    def _failed(
        self,
        trial_id: str,
        run_id: str,
        instance: BenchmarkInstance,
        model: ModelSpec,
        code: str,
        message: str,
        start: float,
    ) -> TrialResult:
        return TrialResult(
            trial_id=trial_id,
            run_id=run_id,
            instance_id=instance.instance_id,
            model_id=model.id,
            behavior_id=instance.behavior_id,
            status=TrialStatus.FAILED,
            error=message,
            error_code=code,
            latency_ms=(time.monotonic() - start) * 1000,
        )

    def _unsupported(
        self,
        trial_id: str,
        run_id: str,
        instance: BenchmarkInstance,
        model: ModelSpec,
        exc: Exception,
    ) -> TrialResult:
        return TrialResult(
            trial_id=trial_id,
            run_id=run_id,
            instance_id=instance.instance_id,
            model_id=model.id,
            behavior_id=instance.behavior_id,
            status=TrialStatus.UNSUPPORTED,
            error=str(exc),
            error_code=UnsupportedModelCapability.code,
        )
