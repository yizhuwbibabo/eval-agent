# Failure taxonomy

Failures are classified with stable, flat identifiers `ROOT.LEAF`
(`schemas/diagnosis.py`). One case may have a primary category plus contributing
factors. Evidence strength and unresolved hypotheses are recorded separately.

```
MODEL_BEHAVIOR
├── WRONG_TOOL_SELECTION
├── INVALID_TOOL_ARGUMENTS
├── INSTRUCTION_VIOLATION
├── ERROR_RECOVERY_FAILURE
├── MISSING_PREREQUISITE_CHECK
├── UNSAFE_ACTION
├── UNSUPPORTED_SUCCESS_CLAIM
└── INCOMPLETE_TASK_REPORTING

HARNESS
├── TOOL_SCHEMA_MISMATCH
├── CONTEXT_INJECTION_ERROR
├── STATE_MANAGEMENT_ERROR
└── TOOL_ORCHESTRATION_ERROR

ENVIRONMENT
├── TOOL_UNAVAILABLE
├── NETWORK_FAILURE
├── PERMISSION_DENIED
└── DEPENDENCY_FAILURE

DATA
├── INCOMPLETE_TRACE
├── INVALID_CUT
├── MISSING_EVIDENCE
└── CONTEXT_CORRUPTION

EVALUATOR
├── RUBRIC_AMBIGUITY
├── GRADER_DISAGREEMENT
├── GRADER_EXECUTION_ERROR
└── INVALID_TEST_CASE

UNKNOWN
└── INSUFFICIENT_EVIDENCE
```

## Attribution rules

- A `FAIL` verdict maps to `MODEL_BEHAVIOR.*` via the override rule
  (`tool_name_validity` → `WRONG_TOOL_SELECTION`, `tool_argument_required_fields`
  → `INVALID_TOOL_ARGUMENTS`) or the violated rubric criteria.
- `UNSUPPORTED` trials map to `HARNESS.TOOL_SCHEMA_MISMATCH` and are **not**
  model failures.
- `FAILED` trials with infrastructure error codes map to `ENVIRONMENT.*`.
- Grader errors map to `EVALUATOR.GRADER_EXECUTION_ERROR`.
- Insufficient evidence maps to `UNKNOWN.INSUFFICIENT_EVIDENCE`.

## Evidence strength

Each evidence item is tagged:

- `OBSERVED_FACT` — read directly from the trace, the response, or a rule hit.
- `SUPPORTED_INFERENCE` — inferred from observations (e.g. category assignment).
- `UNVERIFIED_HYPOTHESIS` — a candidate explanation (e.g. why the model behaved
  that way) that cannot be confirmed from observations.
- `UNKNOWN` — nothing reliable can be said.

Model behavior failures are never given a confirmed root cause: the observed
behavior does not by itself establish whether the cause is training data, prompt
design, or another model-side factor. The diagnosis records this boundary
explicitly and does not emit uncalibrated confidence percentages.

## Clustering

Clustering is over verified structured attributes (behavior, category, model,
rule) — never unverified semantic similarity. Embedding-based clustering is an
optional future extension and, if added, must render reviewable clusters.
