# Operations

## Install

```bash
python -m pip install -e ".[dev]"          # dev + test + lint + typecheck
python -m pip install -e ".[inspect]"      # + Inspect AI integration
```

Requires Python ≥ 3.10. No API keys are needed for offline runs.

## Configuration

- App settings via `AGENTEVALOPS_*` env vars (see `.env.example`):
  `DATABASE_URL`, `ARTIFACT_ROOT`, `BENCHMARK_ROOT`, `LOG_LEVEL`, `LOG_JSON`,
  `ENVIRONMENT`, `ALLOW_EXTERNAL_RAW_TRACES`.
- Evaluation config via `configs/{development,test,production}.yaml`
  (`agenteval run --config ...`).

## CLI

```
agenteval ingest   --input <traces.jsonl|.eval> [--importer jsonl|inspect] [--output out.jsonl]
agenteval validate --input <traces> [--output report.json]
agenteval benchmark build --behavior all|id --source <traces> [--benchmark-id --version]
agenteval benchmark inspect --benchmark-id <id> [--version]
agenteval run    --config <cfg> [--run-id id] [--resume]
agenteval score  --run-id id --config <cfg>
agenteval analyze --run-id id
agenteval report --run-id id [--format md|html|json|all]
agenteval compare --baseline id1 --candidate id2
agenteval review --run-id id --instance-id i --model-id m --decision confirm|reject|flag
```

## Persistence

Default is SQLite at `.agentevalops/agentevalops.db`. For Postgres set
`AGENTEVALOPS_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db` and
`pip install psycopg[binary]`. Migrations apply automatically on first use.

## Observability

Structured JSON logging (`LOG_JSON=true`) with standard fields (run_id,
instance_id, model_id, behavior_id, component, event, status, duration). A
lightweight in-process tracer (`observability/spans.py`) instruments key stages;
a full OpenTelemetry SDK export is a Phase 2 item. Private prompts/tool outputs
are never attached to spans.

## Docker

`docker compose up -d` starts Postgres + the app image. Without Docker, the
offline Python commands work standalone.

## Security notes

- Traces are untrusted input; never executed.
- Generative anchors are not enabled (v1 is review-only / predefined anchors).
- Redaction is on by default; unredacted traces are not sent to external models
  unless explicitly allowed.
- Diagnoses only recommend actions; nothing destructive is auto-applied.
