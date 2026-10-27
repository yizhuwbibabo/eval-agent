"""Failure diagnosis engine tests."""

from __future__ import annotations

from agentevalops.diagnostics.engine import DiagnosisEngine
from agentevalops.evaluation.prompting import build_prompt
from agentevalops.evaluation.providers.mock import compliant, error_prone, wrong_tool
from agentevalops.grading.deterministic import evaluate_deterministic
from agentevalops.grading.hybrid import merge
from agentevalops.grading.llm_judge import MockRubricJudge
from agentevalops.schemas.diagnosis import FailureCategory
from agentevalops.schemas.evaluation import TrialResult, TrialStatus
from agentevalops.schemas.grading import GradingResult

engine = DiagnosisEngine()
judge = MockRubricJudge()


def _grade(inst, turn, rubric, trial_id="t0"):
    hits = evaluate_deterministic(inst, turn)
    verdict = judge._grade_sync(inst, turn, rubric)
    hybrid = merge(hits, verdict, "hybrid", rubric.pass_threshold)
    return GradingResult(
        trial_id=trial_id,
        run_id="r",
        instance_id=inst.instance_id,
        model_id="m",
        behavior_id=inst.behavior_id,
        deterministic_hits=hits,
        rubric_verdict=verdict,
        hybrid=hybrid,
    )


def _trial(inst, model="m", status=TrialStatus.COMPLETED, error=None, error_code=None):
    return TrialResult(
        trial_id="t0",
        run_id="r",
        instance_id=inst.instance_id,
        model_id=model,
        behavior_id=inst.behavior_id,
        status=status,
        error=error,
        error_code=error_code,
    )


def test_error_recovery_failure_category(registry, instances) -> None:
    inst = instances["syn_error_correction_wrong::e4"]
    g = _grade(inst, error_prone(build_prompt(inst)), registry.get(inst.behavior_id).rubric)
    d = engine.diagnose(inst, _trial(inst), g)
    assert d is not None and d.failed
    assert d.primary_category == FailureCategory.MODEL_BEHAVIOR_ERROR_RECOVERY_FAILURE
    assert d.root_cause_confirmable is False
    assert any(e.strength.value == "OBSERVED_FACT" for e in d.evidence)


def test_missing_prerequisite_check_category(registry, instances) -> None:
    inst = instances["syn_log_inspection_wrong::e4"]
    g = _grade(inst, error_prone(build_prompt(inst)), registry.get(inst.behavior_id).rubric)
    d = engine.diagnose(inst, _trial(inst), g)
    assert d.primary_category == FailureCategory.MODEL_BEHAVIOR_MISSING_PREREQUISITE_CHECK


def test_unsupported_success_claim_category(registry, instances) -> None:
    inst = instances["syn_post_edit_wrong::e5"]
    g = _grade(inst, error_prone(build_prompt(inst)), registry.get(inst.behavior_id).rubric)
    d = engine.diagnose(inst, _trial(inst), g)
    assert d.primary_category == FailureCategory.MODEL_BEHAVIOR_UNSUPPORTED_SUCCESS_CLAIM


def test_unsafe_action_category(registry, instances) -> None:
    inst = instances["syn_unsafe_wrong::e3"]
    g = _grade(inst, error_prone(build_prompt(inst)), registry.get(inst.behavior_id).rubric)
    d = engine.diagnose(inst, _trial(inst), g)
    assert d.primary_category == FailureCategory.MODEL_BEHAVIOR_UNSAFE_ACTION


def test_wrong_tool_selection_category(registry, instances) -> None:
    inst = instances["syn_error_correction_wrong::e4"]
    g = _grade(inst, wrong_tool(build_prompt(inst)), registry.get(inst.behavior_id).rubric)
    d = engine.diagnose(inst, _trial(inst), g)
    assert d.primary_category == FailureCategory.MODEL_BEHAVIOR_WRONG_TOOL_SELECTION


def test_passing_trial_has_no_diagnosis(registry, instances) -> None:
    inst = instances["syn_error_correction_wrong::e4"]
    g = _grade(inst, compliant(build_prompt(inst)), registry.get(inst.behavior_id).rubric)
    assert engine.diagnose(inst, _trial(inst), g) is None


def test_unsupported_trial_not_model_failure(registry, instances) -> None:
    inst = instances["syn_error_correction_wrong::e4"]
    t = _trial(inst, status=TrialStatus.UNSUPPORTED, error="no tool support")
    d = engine.diagnose(inst, t, None)
    assert d is not None and d.failed is False
    assert d.primary_category == FailureCategory.HARNESS_TOOL_SCHEMA_MISMATCH
    assert d.root_cause_confirmable is True


def test_infra_failure_not_model_failure(registry, instances) -> None:
    inst = instances["syn_error_correction_wrong::e4"]
    t = _trial(inst, status=TrialStatus.FAILED, error="timeout", error_code="TIMEOUT")
    d = engine.diagnose(inst, t, None)
    assert d is not None and d.failed is False
    assert d.primary_category == FailureCategory.ENVIRONMENT_NETWORK_FAILURE


def test_grader_error_category(registry, instances) -> None:
    inst = instances["syn_error_correction_wrong::e4"]
    g = GradingResult(
        trial_id="t0",
        run_id="r",
        instance_id=inst.instance_id,
        model_id="m",
        behavior_id=inst.behavior_id,
    )
    from agentevalops.schemas.grading import GradeStatus, HybridVerdict

    g.hybrid = HybridVerdict(strategy="hybrid", status=GradeStatus.ERROR)
    d = engine.diagnose(inst, _trial(inst), g)
    assert d.primary_category == FailureCategory.EVALUATOR_GRADER_EXECUTION_ERROR


def test_no_evidence_does_not_fabricate(registry, instances) -> None:
    inst = instances["syn_error_correction_wrong::e4"]
    g = _grade(inst, error_prone(build_prompt(inst)), registry.get(inst.behavior_id).rubric)
    d = engine.diagnose(inst, _trial(inst), g)
    # Root cause is never claimed for a model behavior failure.
    assert d.root_cause_confirmable is False
    assert d.hypotheses
