"""Re-scoring of existing model responses against a rubric version.

Grading is separated from model execution, so saved responses can be re-scored
when a rubric version changes without re-running the models.
"""

from __future__ import annotations

from agentevalops.grading.deterministic import evaluate_deterministic
from agentevalops.grading.hybrid import merge
from agentevalops.grading.llm_judge import RubricJudge
from agentevalops.schemas.behavior import Rubric
from agentevalops.schemas.benchmark import BenchmarkInstance
from agentevalops.schemas.evaluation import TrialResult
from agentevalops.schemas.grading import GradingResult


async def score_trial(
    instance: BenchmarkInstance,
    trial: TrialResult,
    rubric: Rubric,
    judge: RubricJudge,
    strategy: str,
    pass_threshold: float,
    grader_version: str,
) -> GradingResult:
    """Grade a single completed trial. Non-completed trials are not model failures."""
    if trial.status.value != "COMPLETED" or trial.response is None:
        return GradingResult(
            trial_id=trial.trial_id,
            run_id=trial.run_id,
            instance_id=instance.instance_id,
            model_id=trial.model_id,
            behavior_id=instance.behavior_id,
            grader_version=grader_version,
        )
    hits = evaluate_deterministic(instance, trial.response)
    verdict = await judge.grade(instance, trial.response, rubric)
    hybrid = merge(hits, verdict, strategy, pass_threshold)
    return GradingResult(
        trial_id=trial.trial_id,
        run_id=trial.run_id,
        instance_id=instance.instance_id,
        model_id=trial.model_id,
        behavior_id=instance.behavior_id,
        deterministic_hits=hits,
        rubric_verdict=verdict,
        hybrid=hybrid,
        grader_version=grader_version,
    )
