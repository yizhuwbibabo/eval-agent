"""Failure taxonomy.

The taxonomy is defined once here and referenced by the diagnosis engine and
the reporting layer. Categories are flat, stable identifiers (``ROOT.LEAF``)
that survive versioning; the nested view is for documentation and display.
"""

from __future__ import annotations

from agentevalops.schemas.diagnosis import FailureCategory

TAXONOMY: dict[str, list[str]] = {
    "MODEL_BEHAVIOR": [
        "WRONG_TOOL_SELECTION",
        "INVALID_TOOL_ARGUMENTS",
        "INSTRUCTION_VIOLATION",
        "ERROR_RECOVERY_FAILURE",
        "MISSING_PREREQUISITE_CHECK",
        "UNSAFE_ACTION",
        "UNSUPPORTED_SUCCESS_CLAIM",
        "INCOMPLETE_TASK_REPORTING",
    ],
    "HARNESS": [
        "TOOL_SCHEMA_MISMATCH",
        "CONTEXT_INJECTION_ERROR",
        "STATE_MANAGEMENT_ERROR",
        "TOOL_ORCHESTRATION_ERROR",
    ],
    "ENVIRONMENT": [
        "TOOL_UNAVAILABLE",
        "NETWORK_FAILURE",
        "PERMISSION_DENIED",
        "DEPENDENCY_FAILURE",
    ],
    "DATA": [
        "INCOMPLETE_TRACE",
        "INVALID_CUT",
        "MISSING_EVIDENCE",
        "CONTEXT_CORRUPTION",
    ],
    "EVALUATOR": [
        "RUBRIC_AMBIGUITY",
        "GRADER_DISAGREEMENT",
        "GRADER_EXECUTION_ERROR",
        "INVALID_TEST_CASE",
    ],
    "UNKNOWN": ["INSUFFICIENT_EVIDENCE"],
}


def category_of(root: str, leaf: str) -> FailureCategory:
    return FailureCategory(f"{root}.{leaf}")


def is_model_behavior(category: FailureCategory) -> bool:
    return category.root == "MODEL_BEHAVIOR"


def humanize(category: FailureCategory) -> str:
    return f"{category.root.title().replace('_', ' ')} / {category.leaf.replace('_', ' ').title()}"
