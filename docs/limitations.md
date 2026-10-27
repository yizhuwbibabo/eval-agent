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
  OpenAI-compatible provider is wired in but requires an API key; no real model
  run is claimed.
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
- **Production behavior** — all shipped data is `dataset_source="synthetic"` and
  is never presented as production traces.

## Inspect adapter caveats

The Inspect `@tool` decorator derives JSON schemas from typed function
signatures; the adapter registers each tool name/description with a generic
`**kwargs` callable (tools are never executed in decision-point eval). Rich
parameter schemas are preserved in the native runner path, not in the Inspect
adapter. The full native runner remains the authoritative offline path.
