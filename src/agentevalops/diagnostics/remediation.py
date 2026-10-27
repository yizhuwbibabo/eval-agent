"""Remediation recommendations.

Each failure category maps to concrete engineering actions that point at a
specific module - never a blanket "optimize the prompt" or "train the model".
"""

from __future__ import annotations

from agentevalops.schemas.diagnosis import FailureCategory, RemediationAction

REMEDIATIONS: dict[FailureCategory, list[RemediationAction]] = {
    FailureCategory.MODEL_BEHAVIOR_WRONG_TOOL_SELECTION: [
        RemediationAction(
            target_module="benchmark.cutting / evaluation.prompting",
            action="Review tool definitions and the decision-point system prompt; verify the model receives the correct tool set.",
        ),
        RemediationAction(
            target_module="feedback.export",
            action="Add this verified wrong-response case to training candidates with a correct-tool preference pair.",
        ),
    ],
    FailureCategory.MODEL_BEHAVIOR_INVALID_TOOL_ARGUMENTS: [
        RemediationAction(
            target_module="evaluation.providers / tool definitions",
            action="Tighten tool argument JSON schemas and validate required fields before dispatch.",
        ),
        RemediationAction(
            target_module="grading.deterministic",
            action="Confirm the argument-schema rule encodes the intended contract; adjust if over-strict.",
        ),
    ],
    FailureCategory.MODEL_BEHAVIOR_ERROR_RECOVERY_FAILURE: [
        RemediationAction(
            target_module="benchmark.behaviors / prompt",
            action="Add verified error-recovery examples to the prompt or fine-tuning set; re-test against the frozen benchmark.",
        ),
    ],
    FailureCategory.MODEL_BEHAVIOR_MISSING_PREREQUISITE_CHECK: [
        RemediationAction(
            target_module="benchmark.behaviors",
            action="Add a prerequisite-check step (read logs before retry) to the agent harness instructions.",
        ),
    ],
    FailureCategory.MODEL_BEHAVIOR_UNSAFE_ACTION: [
        RemediationAction(
            target_module="evaluation / harness",
            action="Add a confirmation gate to the harness for destructive tools; block unconfirmed destructive calls.",
        ),
        RemediationAction(
            target_module="feedback.export",
            action="Flag as high-severity for human review and preference-pair construction.",
        ),
    ],
    FailureCategory.MODEL_BEHAVIOR_UNSUPPORTED_SUCCESS_CLAIM: [
        RemediationAction(
            target_module="benchmark.behaviors",
            action="Require verification evidence before any completion claim; surface verification tool results in the prompt.",
        ),
    ],
    FailureCategory.HARNESS_TOOL_SCHEMA_MISMATCH: [
        RemediationAction(
            target_module="evaluation.inspect_tasks / providers",
            action="Align tool definitions between the harness and the model provider; mark unsupported capabilities as UNSUPPORTED.",
        ),
    ],
    FailureCategory.ENVIRONMENT_NETWORK_FAILURE: [
        RemediationAction(
            target_module="evaluation.runner",
            action="Increase retry budget and backoff for transient network errors; do not score as model failure.",
        ),
    ],
    FailureCategory.ENVIRONMENT_TOOL_UNAVAILABLE: [
        RemediationAction(
            target_module="tool environment",
            action="Verify the tool is deployed and reachable before the run; record availability in run metadata.",
        ),
    ],
    FailureCategory.ENVIRONMENT_DEPENDENCY_FAILURE: [
        RemediationAction(
            target_module="tool environment",
            action="Pin and validate tool dependencies; add health checks to the harness.",
        ),
    ],
    FailureCategory.EVALUATOR_GRADER_EXECUTION_ERROR: [
        RemediationAction(
            target_module="grading.llm_judge",
            action="Investigate the judge backend failure; re-score the affected trials after fixing the judge.",
        ),
    ],
    FailureCategory.UNKNOWN_INSUFFICIENT_EVIDENCE: [
        RemediationAction(
            target_module="benchmark.confirmation / cutting",
            action="Review the cut for insufficient context; consider excluding the instance or adding evidence.",
        ),
    ],
}


def remediation_for(category: FailureCategory) -> list[RemediationAction]:
    return REMEDIATIONS.get(category, [])
