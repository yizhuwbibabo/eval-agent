# Known limitations

This document records what is *not* implemented and what cannot be concluded
from current data, so the system's claims stay honest.

## Not implemented (by design, v1)

- **Anchor Synthesis Loop** — automatic generation of new anchors is a Phase 2
  capability and is disabled for safety. Only predefined anchors run.
- **A full front-end** — Inspect View covers raw log inspection; reports are
  Markdown/HTML/JSON. A FastAPI admin API was intentionally omitted to avoid
  unnecessary complexity.
- **Large-scale human review UI** — human review is a CLI + persistence
  workflow, not a web UI.
- **Real-model evaluation** — the offline path uses mock models. A real
  OpenAI-compatible provider is wired in (`openai_compat`, via
  `OPENAI_API_KEY` / `OPENAI_BASE_URL`) and a production config is provided, but
  no real-model run is claimed; results in this repository are mock-model only.
- **Real LLM judge** — `judge: llm` requires wiring a `TextCompletionBackend`;
  production configs use the offline rubric judge (`judge: mock`) in the hybrid
  grader.
- **Embedding-based failure clustering** — clustering is over structured
  attributes only; no unverified semantic similarity is used.
- **Full OpenTelemetry export** — a lightweight tracer exists; OTel SDK wiring
  is Phase 2.

## Conclusions that cannot be drawn from current data

- **Grader accuracy** — no human labels are present, so agreement/kappa/
  precision/recall are not reported (the code supports them once labels exist).
- **Model root causes** — for model behavior failures the diagnosis explicitly
  states the underlying cause (training data vs prompt vs capability) is not
  established.
- **Statistical significance** — the synthetic dataset has few instances per
  behavior; bootstrap CIs are wide and conclusions about model ranking are
  unstable. Real-model comparisons require a larger, independent held-out set.
- **Production behavior** — all *synthetic* data is `dataset_source="synthetic"` and
  is never presented as production traces. Real public trajectories are labeled
  `source_type="real"` and keep their provenance metadata.

## Public dataset caveats

- **AgentTrek is step-level** (`xlangai/AgentTrek`): each record is a single
  `system` + `user` + `assistant` triple with the action embedded in assistant
  content as `<action> fn(args) </action>`. It has no tool-result loop and no
  failure/verification structure, so it cannot supply the four first-version
  failure behaviors. The `AgentTrekImporter` maps it to single-turn traces
  (ACTION-frame decision points only) rather than fabricating results.
- **Recovery trajectories carry PII-shaped email addresses**
  (`GurkanOz/tool-failure-recovery-trajectories`): email-domain records contain
  synthetic addresses in tool arguments. The redaction/quality layer correctly
  quarantines these 79/682 records; `scripts/run_real_data.py` excludes
  quarantined traces from benchmark construction.
- **`tool_failure_recovery` is scoped to `openai_chat` traces** via its
  `context_filter`, so it is not exercised by the synthetic `mock_agent`
  dataset (which covers the other four behaviors).
- **τ-bench / SWE-agent importers** are not dedicated yet. τ-bench and other
  OpenAI-tool-calling exports can often be ingested by `OpenAIChatImporter`
  (which reads `{"messages": [...], "tools": [...]}`), but schema-specific
  fields (reward, task metadata) are not yet normalized.
- **Human calibration labels** require human review of *both* passes and
  failures; the review CLI currently targets diagnosed (failed) cases, so
  recall/precision should be read with that sampling in mind until pass-side
  labels are added.

## Inspect adapter caveats

The Inspect `@tool` decorator derives JSON schemas from typed function
signatures; the adapter registers each tool name/description with a generic
`**kwargs` callable (tools are never executed in decision-point eval). Rich
parameter schemas are preserved in the native runner path, not in the Inspect
adapter. The full native runner remains the authoritative offline path.
