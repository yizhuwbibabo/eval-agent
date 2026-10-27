# Evaluation protocol

## Decision-point continuation

The unit of evaluation is a **decision point** carved from a source trace. The
model under test receives the conversation context up to (and including, for
FAILURE frames) the decision point, plus tool definitions, and produces its
**next assistant turn** — text and/or one or more tool calls. Tool calls are
never executed. This mirrors the TraceDance "decision-point continuation" idea:
the source agent's actual continuation is held out and used only for audit.

## Cut modes

- **ACTION** — keep context before the target action turn; drop the action turn.
- **FAILURE** — keep the observed failure and its history; drop the source's
  next turn.
- **CLAIM** — keep the work and results; drop the source's completion claim.

A dedicated leak check (`cutting/leak_check.py`) asserts the source continuation
(events or content) never appears in the context handed to the model. The cutter
also excludes decision points whose next turn would be fully determined by the
harness (e.g. empty context after trimming).

## Models

Models are configured in `configs/*.yaml` (`models: [{id, provider_model,
provider}]`) and selected at run time. The evaluation business logic never
hard-codes a model.

- `provider: mock` — deterministic offline profiles: `compliant`, `error_prone`,
  `wrong_tool`.
- `provider: openai_compat` — any OpenAI-compatible `/chat/completions` endpoint;
  requires `OPENAI_API_KEY`.
- `provider: inspect` (via the Inspect adapter) — `mock/...` mock models inside
  Inspect.

A provider that cannot support the required tool-calling contract marks the
trial `UNSUPPORTED` (never a model failure), and tool calls are never coerced to
plain text to fake a fair comparison.

## Run reliability

- Async execution with a concurrency semaphore.
- Per-trial timeout; retry with exponential backoff **only** on infrastructure
  errors (`TIMEOUT`, `RATE_LIMIT`, `PROVIDER_UNAVAILABLE`).
- Deterministic trial IDs; resume skips already-`COMPLETED` trials.
- Checkpointing: each trial is persisted as it completes.
- The run records a full config snapshot and the provider-reported model
  version in each response's `provider_metadata`.

Run and trial states: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`,
`UNSUPPORTED`.

## End-to-end flow

```
Trace import → validation → anchor recall → confirmation → cut → benchmark
    → multi-model evaluation → grading → diagnosis → metrics → report
```

The offline end-to-end test uses two mock models with distinct behaviors and
verifies the report names the failing model, instance, expected/observed
behavior, violated rule, supporting evidence, failure category, whether root
cause is confirmable, and a recommended action.

## Multi-trial stability

`trials_per_instance` repeats each instance; pass rates are aggregated over
trials. Macro pass rate averages per-behavior rates; micro pass rate pools all
trials. They are reported separately and never conflated.
