"""Command-line interface for AgentEvalOps."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import click

from agentevalops.config import get_settings, load_eval_config
from agentevalops.feedback.review import ReviewService
from agentevalops.ingestion.registry import import_file
from agentevalops.logging_setup import setup_logging
from agentevalops.persistence import get_store
from agentevalops.pipeline import Pipeline
from agentevalops.quality.report import build_quality_report
from agentevalops.redaction import default_redactor
from agentevalops.reporting.data import RunArtifacts
from agentevalops.reporting.regression import compare_runs
from agentevalops.schemas.feedback import HumanReview, ReviewDecision


def _pipeline(store: bool = True) -> Pipeline:
    settings = get_settings()
    return Pipeline(
        behaviors_dir="configs/behaviors",
        benchmark_root=settings.benchmark_root,
        artifact_root=settings.artifact_root,
        database_url=settings.database_url if store else None,
    )


@click.group()
@click.option("--log-level", default=None, help="Logging level override.")
def cli(log_level: str | None) -> None:
    settings = get_settings()
    setup_logging(log_level or settings.log_level, settings.log_json)


@cli.command()
@click.option("--host", default="0.0.0.0", help="Bind host.")
@click.option("--port", default=8000, type=int, help="Bind port.")
def serve(host: str, port: int) -> None:
    """Run the HTTP service (FastAPI + uvicorn)."""
    import uvicorn

    uvicorn.run("agentevalops.server.app:app", host=host, port=port, log_level="info")


# --------------------------------------------------------------------------- #
# Ingest & validate
# --------------------------------------------------------------------------- #


@cli.command()
@click.option("--input", "input_path", required=True, help="Trace file (.jsonl or .eval).")
@click.option("--importer", default=None, help="Importer name (jsonl|inspect); auto-detected if omitted.")
@click.option("--output", default=None, help="Write normalized traces to this JSONL path.")
def ingest(input_path: str, importer: str | None, output: str | None) -> None:
    """Import agent traces into the unified trace schema."""
    result = import_file(input_path, importer)
    click.echo(f"imported {len(result.traces)} traces; {len(result.failed_records)} failed; {len(result.warnings)} warnings")
    for fr in result.failed_records:
        click.echo(f"  [FAILED] record {fr.record_index}: {fr.error}")
    for w in result.warnings:
        click.echo(f"  [WARN] {w.code}: {w.message}")
    if output and result.traces:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            for t in result.traces:
                f.write(t.model_dump_json() + "\n")
        click.echo(f"wrote normalized traces to {output}")


@cli.command()
@click.option("--input", "input_path", required=True, help="Trace file to validate.")
@click.option("--output", default=None, help="Write DataQualityReport JSON to this path.")
def validate(input_path: str, output: str | None) -> None:
    """Run data-quality checks over imported traces."""
    result = import_file(input_path)
    report = build_quality_report(result.traces, default_redactor())
    click.echo(
        f"total={report.total} valid={report.valid} invalid={report.invalid} "
        f"partial={report.partial} quarantined={report.quarantined}"
    )
    for issue in report.issues:
        click.echo(f"  [{issue.severity.value}] {issue.code}: {issue.message}")
    if output:
        Path(output).write_text(report.model_dump_json(indent=2), encoding="utf-8")
        click.echo(f"wrote quality report to {output}")


# --------------------------------------------------------------------------- #
# Benchmark
# --------------------------------------------------------------------------- #


@cli.group()
def benchmark() -> None:
    """Build and inspect behavior benchmarks."""


@benchmark.command("build")
@click.option("--behavior", default="all", help="Behavior id, or 'all'.")
@click.option("--source", "source_path", required=True, help="Traces JSONL file.")
@click.option("--benchmark-id", default="agent_behavior_v1")
@click.option("--version", default="v1")
@click.option("--behaviors", "behaviors_dir", default="configs/behaviors")
def benchmark_build(behavior: str, source_path: str, benchmark_id: str, version: str, behaviors_dir: str) -> None:
    """Build benchmark instances from traces."""
    from agentevalops.benchmark.builder import BenchmarkBuilder
    from agentevalops.benchmark.dataset import DatasetManager
    from agentevalops.benchmark.registry import BehaviorRegistry
    from agentevalops.ingestion.registry import import_file
    from agentevalops.schemas.benchmark import BenchmarkDataset

    registry = BehaviorRegistry.from_dir(behaviors_dir)
    traces = import_file(source_path).traces
    builder = BenchmarkBuilder(registry)
    manager = DatasetManager("datasets")

    behavior_ids = registry.ids() if behavior == "all" else [behavior]
    instances = []
    for bid in behavior_ids:
        res = builder.build(traces, bid, benchmark_id, version)
        s = res.stats
        click.echo(
            f"{bid}: candidates={s.candidate_count} confirmed={s.confirmed_count} "
            f"valid={s.valid_instance_count} invalid={s.invalid_instance_count} quarantined={s.quarantined_count}"
        )
        instances.extend(res.dataset.instances)
    ds = BenchmarkDataset(benchmark_id=benchmark_id, dataset_version=version, instances=instances)
    d = manager.save(ds)
    click.echo(f"built {len(instances)} instances -> {d}")


@benchmark.command("inspect")
@click.option("--benchmark-id", required=True)
@click.option("--version", default="v1")
def benchmark_inspect(benchmark_id: str, version: str) -> None:
    """Inspect a built benchmark dataset."""
    from agentevalops.benchmark.dataset import DatasetManager

    manager = DatasetManager("datasets")
    manifest = manager.manifest(benchmark_id, version)
    if manifest is None:
        click.echo(f"no dataset found for {benchmark_id} v{version}")
        return
    click.echo(
        f"{manifest.benchmark_id} v{manifest.dataset_version}: {manifest.instance_count} instances "
        f"behaviors={manifest.behavior_ids} source={manifest.source_type}"
    )


# --------------------------------------------------------------------------- #
# Run / score / analyze / report
# --------------------------------------------------------------------------- #


def _run_id() -> str:
    return "run_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


@cli.command()
@click.option("--config", "config_path", required=True, help="Eval config YAML.")
@click.option("--run-id", default=None, help="Run id (auto-generated if omitted).")
@click.option("--resume", is_flag=True, help="Skip already-completed trials.")
def run(config_path: str, run_id: str | None, resume: bool) -> None:
    """Run model evaluation over a built benchmark dataset."""
    cfg = load_eval_config(config_path)
    rid = run_id or _run_id()
    pipeline = _pipeline(store=True)
    outcome = asyncio.run(pipeline.run(cfg, rid, resume=resume))
    click.echo(f"run {rid} status={outcome.run.status.value} trials={len(outcome.trials)}")
    from collections import Counter

    click.echo("trial statuses: " + ", ".join(f"{k}={v}" for k, v in Counter(t.status.value for t in outcome.trials).items()))


@cli.command()
@click.option("--run-id", required=True)
@click.option("--config", "config_path", required=True, help="Eval config YAML (grading settings).")
def score(run_id: str, config_path: str) -> None:
    """Grade the responses of a completed run."""
    cfg = load_eval_config(config_path)
    pipeline = _pipeline(store=True)
    gradings = asyncio.run(pipeline.score(run_id, cfg))
    graded = [g for g in gradings if g.hybrid is not None]
    passed = sum(1 for g in graded if g.hybrid and g.hybrid.passed)
    click.echo(f"graded {len(graded)} trials; passed={passed} failed={len(graded) - passed}")


@cli.command()
@click.option("--run-id", required=True)
def analyze(run_id: str) -> None:
    """Run failure diagnosis over a scored run."""
    pipeline = _pipeline(store=True)
    diagnoses = pipeline.analyze(run_id)
    failed = [d for d in diagnoses if d.failed]
    click.echo(f"produced {len(diagnoses)} diagnoses; {len(failed)} model-behavior failures")


@cli.command()
@click.option("--run-id", required=True)
@click.option("--format", "fmt", default="all", type=click.Choice(["md", "html", "json", "all"]))
def report(run_id: str, fmt: str) -> None:
    """Generate the failure analysis report bundle."""
    pipeline = _pipeline(store=True)
    paths = pipeline.report(run_id)
    for kind, p in paths.items():
        click.echo(f"{kind}: {p}")


@cli.command()
@click.option("--baseline", required=True)
@click.option("--candidate", required=True)
def compare(baseline: str, candidate: str) -> None:
    """Compare two runs and emit a regression report."""
    store = get_store(get_settings().database_url)

    def _artifacts(run_id: str) -> RunArtifacts:
        run = store.get_run(run_id)
        if run is None:
            raise click.ClickException(f"unknown run {run_id!r}")
        pipeline = _pipeline(store=True)
        instances = pipeline._load_instances(run.benchmark_id, run.dataset_version)
        behaviors = {b.behavior_id: b for b in pipeline.registry.all()}
        return RunArtifacts(
            run=run,
            trials=store.get_trials(run_id),
            gradings=store.get_gradings(run_id),
            diagnoses=store.get_diagnoses(run_id),
            instances=instances,
            behaviors=behaviors,
        )

    result = compare_runs(_artifacts(baseline), _artifacts(candidate))
    out = get_settings().artifact_root + f"/{candidate}/regression_report.json"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    click.echo(
        f"improved={len(result['improved'])} regressed={len(result['regressed'])} "
        f"unchanged={result['unchanged_count']} newly_invalid={len(result['newly_invalid'])} "
        f"newly_unsupported={len(result['newly_unsupported'])} newly_resolved={len(result['newly_resolved'])}"
    )
    click.echo(f"wrote {out}")


@cli.command()
@click.option("--run-id", required=True)
@click.option("--instance-id", required=True)
@click.option("--model-id", required=True)
@click.option("--decision", required=True, type=click.Choice(["confirm", "reject", "flag"]))
@click.option("--label", default=None, type=bool, help="Ground-truth pass/fail label for calibration.")
@click.option("--reviewer", default="human")
@click.option("--notes", default="")
def review(run_id: str, instance_id: str, model_id: str, decision: str, label: bool | None, reviewer: str, notes: str) -> None:
    """Submit a human review for a diagnosis."""
    store = get_store(get_settings().database_url)
    service = ReviewService(store)
    review = HumanReview(
        review_id=f"REV::{run_id}::{model_id}::{instance_id}",
        run_id=run_id,
        instance_id=instance_id,
        model_id=model_id,
        reviewer=reviewer,
        decision=ReviewDecision(decision),
        label=label,
        notes=notes,
    )
    service.submit(review, store.get_diagnoses(run_id))
    click.echo(f"recorded review {review.review_id}")


@cli.command()
@click.option("--run-id", required=True, help="Run to calibrate against human labels.")
def calibrate(run_id: str) -> None:
    """Report grader agreement with human labels (kappa / precision / recall)."""
    from agentevalops.grading.calibration import calibrate_gradings

    store = get_store(get_settings().database_url)
    gradings = store.get_gradings(run_id)
    reviews = store.get_reviews(run_id)
    labels: dict[str, bool] = {}
    for r in reviews:
        if r.label is None:
            continue
        for g in gradings:
            if g.instance_id == r.instance_id and g.model_id == r.model_id:
                labels[g.trial_id] = r.label
    result = calibrate_gradings(gradings, labels)
    click.echo(json.dumps(result.model_dump(), indent=2))
    if result.n == 0:
        click.echo("No labeled trials found; submit reviews with --label true/false.")


@cli.command("sample-labels")
@click.option("--run-id", required=True, help="Run whose trials to sample.")
@click.option("--output", required=True, help="Path for the labeling JSONL.")
@click.option("--n", default=100, type=int, help="Number of trials to sample.")
@click.option("--seed", default=42, type=int, help="Random seed for reproducibility.")
def sample_labels(run_id: str, output: str, n: int, seed: int) -> None:
    """Emit a stratified labeling batch (passes + failures) for human review."""
    from agentevalops.feedback.labeling import build_label_rows, write_label_rows

    pipeline = _pipeline()
    store = pipeline.store
    assert store is not None
    run = store.get_run(run_id)
    if run is None:
        raise click.ClickException(f"unknown run {run_id!r}")
    gradings = store.get_gradings(run_id)
    trials = {t.trial_id: t for t in store.get_trials(run_id)}
    instances = pipeline._load_instances(run.benchmark_id, run.dataset_version)
    rows = build_label_rows(gradings, trials, instances, n, seed)
    write_label_rows(rows, output)
    click.echo(f"wrote {len(rows)} rows to {output}; fill the 'label' field with true/false.")


@cli.command("ingest-labels")
@click.option("--run-id", required=True, help="Run to attach labels to.")
@click.option("--input", "input_path", required=True, help="Filled labeling JSONL.")
def ingest_labels_cmd(run_id: str, input_path: str) -> None:
    """Ingest filled human labels back into the store."""
    from agentevalops.feedback.labeling import ingest_labels

    store = get_store(get_settings().database_url)
    n = ingest_labels(store, run_id, input_path)
    click.echo(f"ingested {n} labels")


if __name__ == "__main__":
    cli()
