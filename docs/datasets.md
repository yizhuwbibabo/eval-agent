# Real public datasets for behavior benchmarks

What real data can cover each behavior, and how to get it. License and
ground-truth status are recorded so provenance stays honest. All datasets are
public; none are gated behind a login unless noted.

## Already integrated

| Dataset | Behavior | Ground truth | License |
|---|---|---|---|
| `GurkanOz/tool-failure-recovery-trajectories` (recovery_v3.jsonl, 682 traj) | `tool_failure_recovery` | failure markers (opaque) + source retry | public |
| `xlangai/AgentTrek` | ACTION-frame decision points (step-level only) | none | Apache-2.0 |

Download the recovery set: `python scripts/download_recovery_data.py`.

## Recommended next (public, with ground truth)

### τ-bench — multi-turn tool-agent-user interaction
- Repo: https://github.com/sierra-research/tau-bench (Apache-2.0)
- Domains: retail / airline / telecom. Each trajectory = `{task, messages
  (OpenAI tool-calling shape), reward_info}`. `reward_info.reward` is the
  binary task-success label — usable as ground truth for calibration.
- Covers: `tool_failure_recovery`, `error_guided_correction` (tools return
  validation errors with fixes), `failure_log_inspection` (state changes).
- Importer: `TauBenchImporter` (`agentevalops.ingestion.taubench`), preserves
  `reward_info.reward` as `trace.metadata["ground_truth_label"]`.

### SWE-bench Verified — real GitHub issues with verified patches
- HuggingFace: https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified (MIT)
- Each record: `{instance_id, problem_statement, patch, test_patch, ...}` and a
  `resolved` field when a model's patch passes the hidden tests. `resolved` is
  the ground-truth pass/fail of a *candidate fix*.
- Covers: `post_edit_verification` — "did the agent verify its edit before
  claiming success" is the decision point; `resolved` is the outcome label.
- No dedicated importer yet (see `docs/limitations.md`); the patch/verification
  fields need schema-specific normalization.

## Gated / lower-priority

- `cx-cmu/agent_trajectories` — real agent traces, but requires agreeing to
  share contact info (gated); useful later for scale, not required now.

## Ground-truth mapping for the four first-version behaviors

| Behavior | Natural ground-truth label |
|---|---|
| `error_guided_correction` | did the corrected retry succeed? (τ-bench tool result) |
| `failure_log_inspection` | was the eventual retry informed by logs? (τ-bench) |
| `post_edit_verification` | `resolved` (SWE-bench Verified) |
| `unsafe_action_without_confirmation` | rare in public data → human labels or synthetic |

For anything without a natural label, the platform's human-labeling path
(`agenteval sample-labels` → fill → `agenteval ingest-labels` → `agenteval
calibrate`) supplies ground truth.
