# Architecture

## Overview

AgentEvalOps is a layered, offline-first platform that converts raw agent traces
into behavior benchmarks, evaluates models at decision points, and produces
evidence-backed failure diagnoses and reports.

```
Trace Ingestion ──► Benchmark Construction ──► Evaluation ──► Grading
                                                                    │
                        Metrics & Reporting ◄── Failure Analysis ◄──┘
```

Every layer is a package under `src/agentevalops/` with explicit schemas
(`schemas/`) shared across layers. The model under test, the judge and the
scoring rules are all versioned and decoupled from evaluation business logic.

## Design decisions

### Inspect AI as the evaluation framework

The evaluation layer reuses the concepts Inspect AI formalizes — Task / Sample /
Solver / Scorer / eval logs — rather than re-implementing a model execution
engine. The Inspect integration lives in `evaluation/inspect_tasks/` and provides
a custom `Task` with a single-step solver (decision-point continuation never
executes tool calls), a scorer that reuses the shared grading layer, and a mock
model registered via Inspect's `@modelapi` decorator. The adapter is written
against Inspect AI 0.3.x and is import-guarded so the rest of the package runs
without Inspect installed.

A native async runner (`evaluation/runner.py`) is the guaranteed offline path:
concurrency, timeouts, retry-with-backoff (infrastructure errors only), resume,
and checkpointing. It exists because Inspect's model providers are not available
offline without API keys, and because the decision-point continuation semantics
(single turn, no tool execution) are easier to make exact in a small runner.

### TraceDance concepts, adapted

We borrow the *ideas* — deployment traces, behavior specifications, anchors,
confirmation, decision-point cutting — but do **not** claim to reproduce
TraceDance's experiments. The public system is built to run on the user's own
traces. Key adaptations:

- **Anchor-and-confirm split**: anchors (`benchmark/anchors/`) do recall only;
  confirmation (`benchmark/confirmation/`) verifies the behavior actually
  occurred. Anchors are deterministic and report candidate counts, confirmation
  rates and sampled false positives.
- **Decision-point cut modes** (ACTION / FAILURE / CLAIM) with an explicit leak
  check that the source agent's continuation never reaches the model under test.
- **Behavior-specific rubrics** with versioned criteria.
- **LLM-as-a-judge** for confirmation and grading, with structured,
  schema-validated output and `INSUFFICIENT_EVIDENCE` / `ERROR` handling.

### Grading and diagnosis are separate from scoring

Grading produces a verdict with rule hits and evidence. The failure analysis
engine (`diagnostics/engine.py`) then maps those observations into the failure
taxonomy, separating `OBSERVED_FACT` from `SUPPORTED_INFERENCE` and
`UNVERIFIED_HYPOTHESIS`. Root causes are only confirmed for infrastructure /
harness / evaluator / data failures; model behavior failures are explicitly
marked "cannot confirm root cause from observations".

### Persistence

SQLAlchemy 2.x with a SQLite default (fully offline) and a Postgres-compatible
schema via a URL change. Large payloads (responses, evidence) are JSON columns;
raw traces and Inspect eval logs stay as files. A minimal migration runner
(`persistence/migrations.py`) replaces Alembic to avoid a heavyweight dependency;
it applies ordered migrations and records them in `schema_migrations`.

## Layer responsibilities

- **schemas/**: versioned Pydantic models — the single source of truth.
- **ingestion/**: importers (JSONL, Inspect) with explicit data-loss warnings.
- **quality/**: data-quality checks and `VALID/INVALID/PARTIAL/QUARANTINED`
  classification.
- **redaction.py**: configurable regex redaction + secret detection.
- **benchmark/**: behavior registry, anchors, confirmation, cutting, builder,
  dataset persistence.
- **evaluation/**: dataset manager, model registry, providers (mock,
  openai-compat), async runner, Inspect adapter.
- **grading/**: deterministic rules, rubric judges (mock/LLM), hybrid merge,
  calibration.
- **diagnostics/**: taxonomy, evidence-driven engine, remediation, clustering.
- **metrics/**: construction / evaluation / engineering metrics, bootstrap CIs.
- **reporting/**: Markdown / HTML / JSON renderers, comparison, regression.
- **feedback/**: human review, training-candidate export, leakage checks.
- **persistence/**: engine/session, ORM models, repositories, migrations.
- **observability/**: lightweight in-process span recording (OTel-ready).
- **cli/**: the `agenteval` command.

## Error handling

All errors carry a stable `code` (e.g. `TIMEOUT`, `RATE_LIMIT`,
`UNSUPPORTED_MODEL_CAPABILITY`, `GRADER_EXECUTION_ERROR`). The runner retries
only `RETRYABLE_CODES`; model behavior is never retried, and infrastructure
errors are never counted as model failures.
