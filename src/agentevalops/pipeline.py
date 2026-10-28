"""End-to-end pipeline orchestration.

Ties ingestion, benchmark construction, evaluation, grading, diagnosis and
reporting together. The CLI and end-to-end tests both drive this module.
"""

from __future__ import annotations

import asyncio
from typing import Any

from agentevalops.benchmark.builder import BenchmarkBuilder, BuildStats
from agentevalops.benchmark.dataset import DatasetManager
from agentevalops.benchmark.registry import BehaviorRegistry
from agentevalops.config.settings import EvalConfig, Settings, get_settings
from agentevalops.datagen import generate_all
from agentevalops.diagnostics.engine import DiagnosisEngine
from agentevalops.evaluation.models import default_registry
from agentevalops.evaluation.runner import EvalRunner, RunOutcome
from agentevalops.grading.llm_judge import MockRubricJudge, RubricJudge
from agentevalops.grading.rescore import score_trial
from agentevalops.persistence import get_store
from agentevalops.persistence.repositories import Store
from agentevalops.reporting.data import RunArtifacts
from agentevalops.reporting.writer import write_report
from agentevalops.schemas.benchmark import BenchmarkDataset, BenchmarkInstance
from agentevalops.schemas.diagnosis import FailureDiagnosis
from agentevalops.schemas.grading import GradingResult
from agentevalops.schemas.trace import Trace


class Pipeline:
    def __init__(
        self,
        behaviors_dir: str = "configs/behaviors",
        benchmark_root: str = "datasets",
        artifact_root: str = "reports",
        database_url: str | None = None,
    ) -> None:
        self.registry = BehaviorRegistry.from_dir(behaviors_dir)
        self.datasets = DatasetManager(benchmark_root)
        self.artifact_root = artifact_root
        self.store: Store | None = get_store(database_url) if database_url else None
        self.model_registry = default_registry()
        self.diagnosis_engine = DiagnosisEngine()
        self._instances_cache: dict[tuple[str, str], dict[str, BenchmarkInstance]] = {}

    # ------------------------------------------------------------------ #
    def generate_traces(self) -> list[Trace]:
        return generate_all()

    def build_benchmarks(
        self, traces: list[Trace], benchmark_id: str, dataset_version: str
    ) -> tuple[BenchmarkDataset, dict[str, BuildStats]]:
        builder = BenchmarkBuilder(self.registry)
        instances: list[BenchmarkInstance] = []
        stats: dict[str, BuildStats] = {}
        for behavior_id in self.registry.ids():
            result = builder.build(traces, behavior_id, benchmark_id, dataset_version)
            instances.extend(result.dataset.instances)
            stats[behavior_id] = result.stats
        dataset = BenchmarkDataset(
            benchmark_id=benchmark_id, dataset_version=dataset_version, instances=instances
        )
        self.datasets.save(dataset)
        return dataset, stats

    def _load_instances(self, benchmark_id: str, dataset_version: str) -> dict[str, BenchmarkInstance]:
        key = (benchmark_id, dataset_version)
        if key not in self._instances_cache:
            ds = self.datasets.load(benchmark_id, dataset_version)
            self._instances_cache[key] = {i.instance_id: i for i in ds.instances}
        return self._instances_cache[key]

    # ------------------------------------------------------------------ #
    async def run(self, cfg: EvalConfig, run_id: str, resume: bool = False) -> RunOutcome:
        ds = self.datasets.load(cfg.evaluation.dataset, cfg.evaluation.dataset_version)
        runner = EvalRunner(self.model_registry, cfg.execution, cfg.generation, self.store)
        return await runner.run(
            ds,
            cfg.models,
            run_id,
            trials_per_instance=cfg.evaluation.trials_per_instance,
            config_snapshot=cfg.model_dump(mode="json"),
            resume=resume,
        )

    async def score(self, run_id: str, cfg: EvalConfig) -> list[GradingResult]:
        if self.store is None:
            raise RuntimeError("scoring requires a store (database_url)")
        store = self.store
        run = store.get_run(run_id)
        if run is None:
            raise KeyError(f"unknown run {run_id!r}")
        trials = store.get_trials(run_id)
        instances = self._load_instances(run.benchmark_id, run.dataset_version)
        judge = self._judge(cfg)
        sem = asyncio.Semaphore(max(1, cfg.grading.concurrency))

        async def score_one(trial) -> GradingResult | None:
            instance = instances.get(trial.instance_id)
            if instance is None:
                return None
            behavior = self.registry.get(instance.behavior_id)
            async with sem:
                g = await score_trial(
                    instance,
                    trial,
                    behavior.rubric,
                    judge,
                    cfg.grading.strategy,
                    cfg.grading.pass_threshold,
                    cfg.grading.judge_version,
                )
            store.save_grading(g)
            return g

        results = await asyncio.gather(*(score_one(t) for t in trials))
        return [g for g in results if g is not None]

    def _judge(self, cfg: EvalConfig) -> RubricJudge:
        if cfg.grading.judge == "llm":
            import os

            from agentevalops.grading.llm_judge import LLMRubricJudge
            from agentevalops.judge import OpenAICompatBackend

            if not get_settings().allow_external_raw_traces:
                raise RuntimeError(
                    "judge='llm' sends trace context to an external model; "
                    "set AGENTEVALOPS_ALLOW_EXTERNAL_RAW_TRACES=true to opt in"
                )
            api_key = os.environ.get("JUDGE_API_KEY")
            if not api_key:
                raise RuntimeError("judge='llm' requires JUDGE_API_KEY in the environment")
            model = cfg.grading.judge_model or "glm-5"
            base_url = cfg.grading.judge_base_url or "https://open.bigmodel.cn/api/paas/v4"
            backend = OpenAICompatBackend(
                api_key=api_key,
                base_url=base_url,
                model=model,
                extra_body=cfg.grading.judge_config,
            )
            return LLMRubricJudge(backend)
        return MockRubricJudge()

    def analyze(self, run_id: str) -> list[FailureDiagnosis]:
        if self.store is None:
            raise RuntimeError("analysis requires a store (database_url)")
        run = self.store.get_run(run_id)
        if run is None:
            raise KeyError(f"unknown run {run_id!r}")
        trials = self.store.get_trials(run_id)
        gradings = {g.trial_id: g for g in self.store.get_gradings(run_id)}
        instances = self._load_instances(run.benchmark_id, run.dataset_version)
        diagnoses: list[FailureDiagnosis] = []
        for trial in trials:
            instance = instances.get(trial.instance_id)
            if instance is None:
                continue
            d = self.diagnosis_engine.diagnose(instance, trial, gradings.get(trial.trial_id))
            if d is not None:
                diagnoses.append(d)
                self.store.save_diagnosis(d)
        return diagnoses

    def report(self, run_id: str) -> dict[str, str]:
        if self.store is None:
            raise RuntimeError("reporting requires a store (database_url)")
        run = self.store.get_run(run_id)
        if run is None:
            raise KeyError(f"unknown run {run_id!r}")
        trials = self.store.get_trials(run_id)
        gradings = self.store.get_gradings(run_id)
        diagnoses = self.store.get_diagnoses(run_id)
        instances = self._load_instances(run.benchmark_id, run.dataset_version)
        behaviors = {b.behavior_id: b for b in self.registry.all()}
        artifacts = RunArtifacts(
            run=run,
            trials=trials,
            gradings=gradings,
            diagnoses=diagnoses,
            instances=instances,
            behaviors=behaviors,
        )
        return write_report(artifacts, self.artifact_root)

    # ------------------------------------------------------------------ #
    async def full(
        self,
        cfg: EvalConfig,
        run_id: str,
        traces: list[Trace] | None = None,
        benchmark_id: str | None = None,
        dataset_version: str | None = None,
    ) -> dict[str, Any]:
        """Build + run + score + analyze + report in one pass."""
        benchmark_id = benchmark_id or cfg.evaluation.dataset
        dataset_version = dataset_version or cfg.evaluation.dataset_version
        traces = traces or self.generate_traces()
        self.build_benchmarks(traces, benchmark_id, dataset_version)
        await self.run(cfg, run_id)
        await self.score(run_id, cfg)
        self.analyze(run_id)
        paths = self.report(run_id)
        return {"run_id": run_id, "report_paths": paths, "benchmark_id": benchmark_id}


def build_pipeline(settings: Settings | None = None) -> Pipeline:
    settings = settings or get_settings()
    return Pipeline(
        behaviors_dir="configs/behaviors",
        benchmark_root=settings.benchmark_root,
        artifact_root=settings.artifact_root,
        database_url=settings.database_url,
    )
