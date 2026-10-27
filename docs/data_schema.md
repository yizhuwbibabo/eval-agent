# Data schema

The unified trace schema (`schemas/trace.py`) is the canonical intermediate
representation for every importer.

## Trace

```
Trace
├── trace_id           (str, required)
├── session_id         (str | null)
├── source_system      (str, required)      # provenance, e.g. "mock_agent"
├── source_model       (str | null)
├── dataset_source     (str, required)      # "synthetic" | "production" | ...
├── timestamp          (datetime | null)
├── schema_version     (str, default "1.0")
├── metadata           (dict)               # tool_definitions, etc.
└── events             (list[TraceEvent])
```

## TraceEvent

```
TraceEvent
├── event_id           (str, required)
├── event_type         (user | assistant | tool_call | tool_result | system | harness | error)
├── timestamp          (datetime | null)
├── role               (str | null)         # user / assistant / tool / system / harness
├── input_origin       (str | null)         # distinguishes user vs harness messages
├── turn_id            (str | null)         # groups events of one assistant turn
├── content            (str | null)
├── tool_name          (str | null)
├── tool_call_id       (str | null)         # links a tool result to its call
├── tool_arguments     (dict | null)
├── tool_result        (any | null)         # text, structured JSON, or multimodal ref
├── error              (str | null)
├── status             (success | error | pending | cancelled | timeout | null)
└── metadata           (dict)
```

One assistant turn may contain multiple tool calls (same `turn_id`); tool calls
and results are separate events and may be ordered arbitrarily. Missing fields
are `null`, never fabricated.

## Construction entities

- **Trace** — raw input (immutable source version preserved).
- **Candidate** — an anchor recall: `candidate_id`, `behavior_id`,
  `source_trace_id`, `cut_event_id`, anchor name/version, evidence event IDs.
- **ConfirmationResult** — `is_valid`, `target_behavior_observed`,
  `context_sufficient`, `decision_already_made`, evidence, status
  (`confirmed` / `rejected` / `insufficient_evidence` / `unsupported` / `error`).
- **BenchmarkInstance** — `benchmark_id`, `dataset_version`, `instance_id`,
  `behavior_id`, `frame`, `source_trace_id`, `cut_event_id`, rendered `context`,
  `tool_definitions`, `rubric_id`/`rubric_version`, `evidence_references`,
  `cut_metadata`, `validation_status`, `source_type`, `created_at`.
- **BehaviorSpecification** — `behavior_id`, `name`, `description`,
  `behavior_frame`, `anchor_definition`, `confirmation_criteria`,
  `cut_contract`, `rubric` (versioned criteria + pass threshold), `severity`,
  `specification_version`.

## Evaluation & grading entities

- **EvalRun** — run id, benchmark id/version, status, model list, config
  snapshot, timestamps.
- **TrialResult** — trial id, run/instance/model/behavior, status
  (`COMPLETED` / `FAILED` / `UNSUPPORTED` / ...), `response` (AssistantTurn),
  error code, latency, usage, retries.
- **AssistantTurn** — `text`, `tool_calls[]` (name/args/call_id),
  `finish_reason`, `provider_metadata`, `usage`.
- **GradingResult** — deterministic hits, rubric verdict, hybrid verdict,
  grader version.

## Diagnosis entity

`FailureDiagnosis` — primary category (flat `ROOT.LEAF` id), contributing
factors, evidence (`statement` + `strength` + `event_ids`), hypotheses, root
cause confirmability, remediation, review status.

## Versioning & lineage

Traces keep `source_system`/`schema_version`. Behaviors keep
`specification_version`; rubrics keep their own `version`; graders record the
rubric version used. Runs keep a full config snapshot. Original evaluation
results are never silently overwritten — saves are keyed by natural identity.
