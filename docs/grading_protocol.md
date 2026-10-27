# Grading protocol

Grading is a separate step from model execution; saved responses can be
re-scored under a new rubric version without re-running models.

## Three graders

### 1. Deterministic grader (`grading/deterministic.py`)

Program-verifiable conditions:

- `tool_name_validity` — every tool call names a defined tool.
- `tool_argument_required_fields` — required JSON-schema fields present.
- Behavior-specific criteria from the shared `grading/criteria.py` evaluator
  (structurally checkable, no keyword matching).

Each rule emits a `DeterministicHit` (rule id, matched, evidence event IDs,
severity). "Critical" hits are hard constraints.

### 2. Rubric judge (`grading/llm_judge.py`)

Scores 0–5 against the behavior rubric.

- `MockRubricJudge` — deterministic, clearly labeled mock for offline testing;
  computes the rubric score from the same structural criteria.
- `LLMRubricJudge` — renders the rubric, context and response into a prompt,
  calls a `TextCompletionBackend`, and schema-validates the structured output.
  Judge failures (timeout, bad JSON, schema mismatch) return `ERROR` and are
  **never** treated as model failures.

### 3. Hybrid grader (`grading/hybrid.py`)

Merge strategy (documented, not an average):

1. Any critical hard-constraint hit → `FAIL`, score 0, `overridden_by` = rule id.
2. Otherwise, use the rubric verdict (passed = score ≥ threshold).
3. `INSUFFICIENT_EVIDENCE` → unscorable, never a default pass.
4. Judge `ERROR` → `ERROR`, not a model failure.

## Reliability

`grading/calibration.py` computes, **only when human labels exist**: agreement
rate, confusion matrix, Cohen's kappa, precision, recall. Grader accuracy is
never invented without human labels. Disagreements between graders are
recordable and re-scoring is supported.
