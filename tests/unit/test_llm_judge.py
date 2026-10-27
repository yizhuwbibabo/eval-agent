"""Rubric judge tests (mock + LLM backend)."""

from __future__ import annotations

import json

from agentevalops.evaluation.prompting import build_prompt
from agentevalops.evaluation.providers.mock import compliant, error_prone
from agentevalops.grading.llm_judge import LLMRubricJudge, MockRubricJudge
from agentevalops.judge import TextCompletionBackend
from agentevalops.schemas.grading import GradeStatus


class FakeBackend(TextCompletionBackend):
    def __init__(self, responses: list[str] | None = None) -> None:
        self.responses = responses or []
        self.calls = 0

    async def complete(self, system: str, user: str) -> str:
        r = self.responses[self.calls % len(self.responses)]
        self.calls += 1
        return r


def test_mock_judge_scores_compliant(registry, instances) -> None:
    inst = instances["syn_error_correction_wrong::e4"]
    judge = MockRubricJudge()
    verdict = judge._grade_sync(inst, compliant(build_prompt(inst)), registry.get(inst.behavior_id).rubric)
    assert verdict.score == 5.0
    assert verdict.passed is True
    assert verdict.violated_criteria == []


def test_mock_judge_scores_error_prone(registry, instances) -> None:
    inst = instances["syn_error_correction_wrong::e4"]
    judge = MockRubricJudge()
    verdict = judge._grade_sync(inst, error_prone(build_prompt(inst)), registry.get(inst.behavior_id).rubric)
    assert verdict.score == 0.0
    assert verdict.passed is False
    assert "error_correction_applied" in verdict.violated_criteria


async def test_llm_judge_valid_output(registry, instances) -> None:
    inst = instances["syn_error_correction_wrong::e4"]
    backend = FakeBackend([json.dumps({"score": 2, "passed": False, "violated_criteria": ["error_correction_applied"], "evidence": [{"event_id": "e4", "description": "x"}], "reason": "ignored correction"})])
    judge = LLMRubricJudge(backend)
    verdict = await judge.grade(inst, error_prone(build_prompt(inst)), registry.get(inst.behavior_id).rubric)
    assert verdict.status == GradeStatus.GRADED
    assert verdict.score == 2
    assert verdict.passed is False


async def test_llm_judge_invalid_json_is_error(registry, instances) -> None:
    inst = instances["syn_error_correction_wrong::e4"]
    backend = FakeBackend(["not json at all"])
    judge = LLMRubricJudge(backend)
    verdict = await judge.grade(inst, error_prone(build_prompt(inst)), registry.get(inst.behavior_id).rubric)
    assert verdict.status == GradeStatus.ERROR


async def test_llm_judge_schema_mismatch_is_error(registry, instances) -> None:
    inst = instances["syn_error_correction_wrong::e4"]
    backend = FakeBackend([json.dumps({"score": "not-a-number", "passed": "maybe"})])
    judge = LLMRubricJudge(backend)
    verdict = await judge.grade(inst, error_prone(build_prompt(inst)), registry.get(inst.behavior_id).rubric)
    assert verdict.status == GradeStatus.ERROR
