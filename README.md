# AgentEvalOps — Agent Evaluation & Failure Analysis Platform

AgentEvalOps turns raw agent deployment traces into **behavior benchmarks**, evaluates
models at decision points, grades them against **versioned rubrics**, and produces
**evidence-backed failure analysis reports** that locate *where*, *why* and *what
component* is responsible for a failure — rather than emitting a single leaderboard
score.

It answers questions like:

- At which task, context and decision point did the agent fail?
- Was it tool selection, argument construction, error recovery, a missing
  prerequisite check, or an unsafe action?
- Which concrete rule or constraint was violated?
- Which log events, tool results or model responses prove it?
- Is the failure model behavior, the harness, the environment, the data or the
  evaluator — or is there simply not enough evidence?
- What changed between two model/prompt/tool versions (regression)?

The system runs **fully offline** with deterministic mock models; no API key is
required for tests or the end-to-end pipeline.

---

## Quick start

```bash
# 1. Install (Python >= 3.10)
python -m pip install -e ".[dev]"

# 2. Generate synthetic traces and run the full offline pipeline
python scripts/generate_synthetic_traces.py
python scripts/run_e2e.py --config configs/development.yaml

# 3. Inspect the generated report bundle
ls reports/e2e_run/
#   summary.md  detailed_report.html  metrics.json
#   failure_cases.jsonl  model_comparison.csv
```

Or run the pipeline step-by-step through the CLI:

```bash
export PYTHONPATH=src   # if installed non-editable, skip

agenteval ingest  --input datasets/synthetic/traces.jsonl
agenteval validate --input datasets/synthetic/traces.jsonl

agenteval benchmark build --behavior all --source datasets/synthetic/traces.jsonl
agenteval benchmark inspect --benchmark-id agent_behavior_v1

agenteval run     --config configs/development.yaml --run-id run_001
agenteval score   --run-id run_001 --config configs/development.yaml
agenteval analyze --run-id run_001
agenteval report  --run-id run_001 --format all

agenteval compare --baseline run_001 --candidate run_002
```

Run the test suite:

```bash
python -m pytest -q          # fully offline
python -m ruff check src tests
python -m mypy src
```

### Real data + real models

AgentEvalOps ships importers for real public agent trajectories and an
OpenAI-compatible model provider. To run an end-to-end pass over the
[`GurkanOz/tool-failure-recovery-trajectories`](https://huggingface.co/datasets/GurkanOz/tool-failure-recovery-trajectories)
dataset (682 real tool-use trajectories, ~476 failure decision points):

```bash
# offline: deterministic mock models (no API key)
python scripts/run_real_data.py --data data/real/recovery_v3.jsonl

# real model: requires OPENAI_API_KEY (and optionally OPENAI_BASE_URL)
export OPENAI_API_KEY=sk-...
export AGENTEVALOPS_ALLOW_EXTERNAL_RAW_TRACES=true   # opt in to external sends
python scripts/run_real_data.py --config configs/production_recovery.yaml

# e.g. DeepSeek official endpoint (deepseek-flash)
export OPENAI_BASE_URL=https://api.deepseek.com
python scripts/run_real_data.py --config configs/deepseek_recovery.yaml
```

The `openai_compat` provider is fail-closed: it refuses to send traces to an
external model unless `AGENTEVALOPS_ALLOW_EXTERNAL_RAW_TRACES=true` is set
explicitly.

The importer (`src/agentevalops/ingestion/openai_chat.py`) normalizes
OpenAI tool-calling trajectories into the unified Trace schema and detects the
diverse failure signals seen in the wild (`[SOCKET_HANGUP]`,
`[REQUEST_TIMEOUT: ...]`, `{"error": ...}`, malformed JSON, `null`,
`SyntaxError`, parse-fail markers) — not just a single error keyword.

---

## What the platform produces

The report bundle under `reports/<run_id>/` contains:

| File | Purpose |
|---|---|
| `summary.md` | Executive summary: goal, dataset/version, models, pass rates, top failure categories, high-risk failures, recommendations |
| `detailed_report.html` | Self-contained detailed report (per-failure evidence, diagnostic boundary, remediation) |
| `metrics.json` | Full structured metrics (construction / evaluation / engineering) |
| `failure_cases.jsonl` | One machine-readable failure record per failing trial |
| `model_comparison.csv` | Paired model comparison (pass rate, latency, tokens, cost, reliability) |
| `regression_report.json` | (via `compare`) improved / regressed / unchanged / newly-invalid / newly-unsupported / newly-resolved |

Every failure record carries: run, instance, model, behavior, decision frame,
expected vs. observed behavior, verdict, score, primary failure category,
evidence (with event IDs and `OBSERVED_FACT` / `SUPPORTED_INFERENCE` /
`UNVERIFIED_HYPOTHESIS` strength), diagnostic boundary, remediation, and review
status. No uncalibrated confidence percentages are emitted.

---

## Architecture

The system is organized into seven layers. See `docs/architecture.md` for the
full design and the third-party frameworks it builds on (TraceDance concepts,
Anthropic's evals taxonomy, UK AISI's Inspect AI).

```
Trace Ingestion → Benchmark Construction → Evaluation → Grading
        → Failure Analysis → Metrics & Reporting
              (persistence / observability / security across all layers)
```

- **Schemas** (`src/agentevalops/schemas/`): versioned Pydantic models for
  traces, behaviors, benchmark instances, evaluation runs/trials, grading, and
  diagnoses.
- **Ingestion & quality** (`ingestion/`, `quality/`): JSONL + Inspect importers,
  privacy redaction, and data-quality checks with `VALID / INVALID / PARTIAL /
  QUARANTINED` states.
- **Benchmark construction** (`benchmark/`): behavior registry, plugin anchors,
  candidate confirmation, ACTION/FAILURE/CLAIM decision-point cutter with leak
  checks.
- **Evaluation** (`evaluation/`): async runner (concurrency, timeout, retry,
  resume, checkpointing), mock + OpenAI-compatible providers, Inspect AI task
  adapter.
- **Grading** (`grading/`): deterministic rules, rubric LLM judge (mock + real),
  hybrid merge, calibration (agreement / Cohen's kappa / confusion).
- **Failure analysis** (`diagnostics/`): taxonomy, evidence-driven diagnosis
  engine, remediation, clustering.
- **Metrics & reporting** (`metrics/`, `reporting/`): construction/evaluation/
  engineering metrics, bootstrap CIs, Markdown/HTML/JSON reports, regression.
- **Feedback** (`feedback/`): human review, training-candidate export, leakage
  checks.
- **Persistence** (`persistence/`): SQLAlchemy (SQLite default, Postgres-ready),
  migrations.

---

## Behaviors

| Behavior | Frame | Description |
|---|---|---|
| `error_guided_correction` | FAILURE | Tool stated an explicit correction; agent repeated the failing operation |
| `failure_log_inspection` | FAILURE | Background task failed; agent retried/modified without inspecting logs |
| `post_edit_verification` | CLAIM | Agent edited code then claimed success without re-verifying |
| `unsafe_action_without_confirmation` | ACTION | Destructive action prepared without requesting confirmation |
| `tool_failure_recovery` | FAILURE | Tool call failed transiently; agent gave up instead of retrying/recovering (scoped to real `openai_chat` trajectories) |

Behavior specifications are versioned YAML files under `configs/behaviors/`.

---

## Configuration

Three profiles under `configs/`:

- `development.yaml` — fully offline (3 mock models, `trials_per_instance: 3`)
- `test.yaml` — fast offline (2 mock models, `trials_per_instance: 1`)
- `production.yaml` — real OpenAI-compatible provider on the synthetic benchmark (requires `OPENAI_API_KEY`)
- `production_recovery.yaml` — real OpenAI-compatible provider on the real recovery benchmark (requires `OPENAI_API_KEY`)
- `deepseek_recovery.yaml` — DeepSeek official endpoint (`deepseek-flash`, thinking mode disabled) on the real recovery benchmark

Sensitive settings come from environment variables; copy `.env.example` to
`.env`. The privacy gate `AGENTEVALOPS_ALLOW_EXTERNAL_RAW_TRACES` defaults to
`false`, so unredacted private traces are never sent to an external model.

---

## Security

Traces are untrusted input. The system never executes commands or code found in
traces, never runs generative anchors without review, redacts secrets before
storage/reporting, and only ever *recommends* remediations. See
`docs/operations.md` and `docs/limitations.md`.

---

## Documentation

- `docs/architecture.md` — design decisions and third-party framework usage
- `docs/data_schema.md` — unified trace schema and entity model
- `docs/evaluation_protocol.md` — decision-point evaluation protocol
- `docs/grading_protocol.md` — deterministic / LLM / hybrid grading
- `docs/failure_taxonomy.md` — the failure classification taxonomy
- `docs/operations.md` — running, config, persistence, observability
- `docs/limitations.md` — known limitations and what cannot be concluded

---

## License

Apache-2.0.
