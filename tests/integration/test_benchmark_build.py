"""Benchmark build integration tests."""

from __future__ import annotations

from agentevalops.benchmark.builder import BenchmarkBuilder
from agentevalops.benchmark.confirmation.deterministic import DeterministicConfirmer
from agentevalops.benchmark.dataset import DatasetManager
from agentevalops.schemas.benchmark import ConfirmationStatus, InstanceStatus


def test_build_produces_one_instance_per_behavior(registry, traces) -> None:
    builder = BenchmarkBuilder(registry, DeterministicConfirmer())
    for bid in registry.ids():
        result = builder.build(traces, bid, "b", "v1")
        if bid == "tool_failure_recovery":
            # Scoped to real openai_chat tool-use trajectories via its
            # context_filter, so it has no synthetic coverage by design.
            assert result.stats.valid_instance_count == 0, bid
            continue
        assert result.stats.valid_instance_count == 1, bid
        assert result.dataset.instances[0].validation_status == InstanceStatus.VALID


def test_confirmation_result_has_valid_evidence(registry, traces) -> None:
    builder = BenchmarkBuilder(registry, DeterministicConfirmer())
    result = builder.build(traces, "error_guided_correction", "b", "v1")
    confirmed = [c for c in result.confirmations if c.status == ConfirmationStatus.CONFIRMED]
    assert confirmed
    for conf in confirmed:
        for eid in conf.evidence_event_ids:
            # evidence must reference events that exist in some trace
            assert any(t.event_by_id(eid) is not None for t in traces)


def test_invalid_cut_excluded(registry, traces) -> None:
    builder = BenchmarkBuilder(registry, DeterministicConfirmer())
    result = builder.build(traces, "unsafe_action_without_confirmation", "b", "v1")
    # The invalid-cut trace must not produce a valid instance.
    assert result.stats.invalid_instance_count >= 1
    for inst in result.dataset.instances:
        assert inst.source_trace_id != "syn_unsafe_invalid_cut"


def test_dataset_roundtrip(tmp_path, registry, traces) -> None:
    builder = BenchmarkBuilder(registry, DeterministicConfirmer())
    instances = []
    for bid in registry.ids():
        instances.extend(builder.build(traces, bid, "b", "v1").dataset.instances)
    from agentevalops.schemas.benchmark import BenchmarkDataset

    ds = BenchmarkDataset(benchmark_id="b", dataset_version="v1", instances=instances)
    manager = DatasetManager(tmp_path)
    d = manager.save(ds)
    assert (d / "instances.jsonl").exists()
    assert (d / "manifest.json").exists()
    loaded = manager.load("b", "v1")
    assert len(loaded.instances) == len(instances)
    assert loaded.instances[0].cut_metadata == instances[0].cut_metadata


def test_anchor_confirmation_rate_stats(registry, traces) -> None:
    builder = BenchmarkBuilder(registry, DeterministicConfirmer())
    result = builder.build(traces, "error_guided_correction", "b", "v1")
    # 3 candidates (wrong, right, no_continuation): 1 confirmed, 1 rejected, 1 insufficient.
    assert result.stats.candidate_count == 3
    assert result.stats.confirmed_count == 1
    assert result.stats.rejected_count == 1
    assert result.stats.insufficient_evidence_count == 1
