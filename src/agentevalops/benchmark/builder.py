"""Benchmark builder: anchors -> confirmation -> cut -> benchmark instances."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from agentevalops.benchmark.anchors.registry import get_anchor
from agentevalops.benchmark.confirmation.base import Confirmer
from agentevalops.benchmark.confirmation.deterministic import DeterministicConfirmer
from agentevalops.benchmark.cutting.cutter import cut
from agentevalops.benchmark.cutting.leak_check import check_leak
from agentevalops.benchmark.registry import BehaviorRegistry
from agentevalops.schemas.benchmark import (
    BenchmarkDataset,
    BenchmarkInstance,
    Candidate,
    ConfirmationResult,
    ConfirmationStatus,
    InstanceStatus,
)
from agentevalops.schemas.trace import Trace


class BuildStats(BaseModel):
    behavior_id: str
    trace_count: int = 0
    candidate_count: int = 0
    confirmed_count: int = 0
    rejected_count: int = 0
    insufficient_evidence_count: int = 0
    unsupported_count: int = 0
    error_count: int = 0
    valid_instance_count: int = 0
    invalid_instance_count: int = 0
    quarantined_count: int = 0
    anchor_candidates: dict[str, int] = Field(default_factory=dict)

    @property
    def confirmation_rate(self) -> float:
        if self.candidate_count == 0:
            return 0.0
        return self.confirmed_count / self.candidate_count

    @property
    def valid_instance_rate(self) -> float:
        total = self.valid_instance_count + self.invalid_instance_count + self.quarantined_count
        if total == 0:
            return 0.0
        return self.valid_instance_count / total


class BuildResult(BaseModel):
    dataset: BenchmarkDataset
    stats: BuildStats
    confirmations: list[ConfirmationResult] = Field(default_factory=list)
    invalid_instances: list[dict[str, Any]] = Field(default_factory=list)


class BenchmarkBuilder:
    def __init__(self, registry: BehaviorRegistry, confirmer: Confirmer | None = None) -> None:
        self.registry = registry
        self.confirmer = confirmer or DeterministicConfirmer()

    def build(
        self,
        traces: list[Trace],
        behavior_id: str,
        benchmark_id: str,
        dataset_version: str,
        source_type: str = "synthetic",
    ) -> BuildResult:
        behavior = self.registry.get(behavior_id)
        anchor = get_anchor(behavior.anchor_definition.anchor_type)

        by_id = {t.trace_id: t for t in traces}
        candidates: list[Candidate] = []
        anchor_candidates: dict[str, int] = {}
        for trace in traces:
            found = anchor.scan(trace, behavior)
            candidates.extend(found)
            anchor_candidates[anchor.name] = anchor_candidates.get(anchor.name, 0) + len(found)

        stats = BuildStats(behavior_id=behavior_id, trace_count=len(traces), candidate_count=len(candidates), anchor_candidates=anchor_candidates)

        confirmations: list[ConfirmationResult] = []
        instances: list[BenchmarkInstance] = []
        invalid: list[dict[str, Any]] = []

        for cand in candidates:
            cand_trace = by_id.get(cand.source_trace_id)
            if cand_trace is None:
                stats.error_count += 1
                continue
            conf = self.confirmer.confirm(cand_trace, behavior, cand)
            confirmations.append(conf)
            if conf.status == ConfirmationStatus.CONFIRMED:
                stats.confirmed_count += 1
            elif conf.status == ConfirmationStatus.REJECTED:
                stats.rejected_count += 1
            elif conf.status == ConfirmationStatus.INSUFFICIENT_EVIDENCE:
                stats.insufficient_evidence_count += 1
            elif conf.status == ConfirmationStatus.UNSUPPORTED:
                stats.unsupported_count += 1
            else:
                stats.error_count += 1
                continue

            if not conf.confirmed:
                continue

            cut_result = cut(cand_trace, behavior, cand)
            target_events = [
                e for eid in cut_result.target_event_ids if (e := cand_trace.event_by_id(eid)) is not None
            ]
            leaks = check_leak(cut_result.context, target_events)

            if leaks:
                stats.quarantined_count += 1
                invalid.append({"candidate_id": cand.candidate_id, "reason": "leak", "leaks": leaks})
                continue
            if not cut_result.context:
                stats.invalid_instance_count += 1
                invalid.append({"candidate_id": cand.candidate_id, "reason": "empty context"})
                continue

            instance = BenchmarkInstance(
                benchmark_id=benchmark_id,
                dataset_version=dataset_version,
                instance_id=f"{cand.source_trace_id}::{cand.cut_event_id}",
                behavior_id=behavior_id,
                frame=behavior.behavior_frame,
                source_trace_id=cand.source_trace_id,
                cut_event_id=cand.cut_event_id,
                context=cut_result.context,
                tool_definitions=cut_result.tool_definitions,
                rubric_id=behavior.rubric.rubric_id,
                rubric_version=behavior.rubric.version,
                evidence_references=conf.evidence_event_ids,
                cut_metadata=cut_result.cut_metadata,
                validation_status=InstanceStatus.VALID,
                source_type=source_type,
                created_at=datetime.now(timezone.utc),
            )
            instances.append(instance)
            stats.valid_instance_count += 1

        dataset = BenchmarkDataset(
            benchmark_id=benchmark_id,
            dataset_version=dataset_version,
            instances=instances,
            metadata={
                "behavior_id": behavior_id,
                "behavior_version": behavior.specification_version,
                "source_type": source_type,
                "built_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return BuildResult(dataset=dataset, stats=stats, confirmations=confirmations, invalid_instances=invalid)

    async def build_async(
        self,
        traces: list[Trace],
        behavior_id: str,
        benchmark_id: str,
        dataset_version: str,
        source_type: str = "synthetic",
    ) -> BuildResult:
        """Async variant for async confirmers (e.g. LLMConfirmer)."""
        behavior = self.registry.get(behavior_id)
        anchor = get_anchor(behavior.anchor_definition.anchor_type)
        by_id = {t.trace_id: t for t in traces}
        candidates: list[Candidate] = []
        for trace in traces:
            candidates.extend(anchor.scan(trace, behavior))

        stats = BuildStats(behavior_id=behavior_id, trace_count=len(traces), candidate_count=len(candidates))
        confirmations: list[ConfirmationResult] = []
        instances: list[BenchmarkInstance] = []
        invalid: list[dict[str, Any]] = []

        for cand in candidates:
            cand_trace = by_id.get(cand.source_trace_id)
            if cand_trace is None:
                stats.error_count += 1
                continue
            conf = await self.confirmer.aconfirm(cand_trace, behavior, cand)
            confirmations.append(conf)
            self._classify_confirmation(conf, stats)
            if not conf.confirmed:
                continue

            cut_result = cut(cand_trace, behavior, cand)
            target_events = [
                e for eid in cut_result.target_event_ids if (e := cand_trace.event_by_id(eid)) is not None
            ]
            leaks = check_leak(cut_result.context, target_events)
            if leaks or not cut_result.context:
                stats.invalid_instance_count += 1
                invalid.append({"candidate_id": cand.candidate_id, "reason": "leak" if leaks else "empty context"})
                continue
            instances.append(
                BenchmarkInstance(
                    benchmark_id=benchmark_id,
                    dataset_version=dataset_version,
                    instance_id=f"{cand.source_trace_id}::{cand.cut_event_id}",
                    behavior_id=behavior_id,
                    frame=behavior.behavior_frame,
                    source_trace_id=cand.source_trace_id,
                    cut_event_id=cand.cut_event_id,
                    context=cut_result.context,
                    tool_definitions=cut_result.tool_definitions,
                    rubric_id=behavior.rubric.rubric_id,
                    rubric_version=behavior.rubric.version,
                    evidence_references=conf.evidence_event_ids,
                    cut_metadata=cut_result.cut_metadata,
                    validation_status=InstanceStatus.VALID,
                    source_type=source_type,
                    created_at=datetime.now(timezone.utc),
                )
            )
            stats.valid_instance_count += 1

        dataset = BenchmarkDataset(
            benchmark_id=benchmark_id,
            dataset_version=dataset_version,
            instances=instances,
            metadata={"behavior_id": behavior_id, "source_type": source_type},
        )
        return BuildResult(dataset=dataset, stats=stats, confirmations=confirmations, invalid_instances=invalid)

    @staticmethod
    def _classify_confirmation(conf: ConfirmationResult, stats: BuildStats) -> None:
        if conf.status == ConfirmationStatus.CONFIRMED:
            stats.confirmed_count += 1
        elif conf.status == ConfirmationStatus.REJECTED:
            stats.rejected_count += 1
        elif conf.status == ConfirmationStatus.INSUFFICIENT_EVIDENCE:
            stats.insufficient_evidence_count += 1
        elif conf.status == ConfirmationStatus.UNSUPPORTED:
            stats.unsupported_count += 1
        else:
            stats.error_count += 1
