# Real public datasets

This directory holds real public agent trajectories, downloaded on demand for
end-to-end runs. The raw files are git-ignored (reproducible from source).

## tool-failure-recovery-trajectories

- Source: https://huggingface.co/datasets/GurkanOz/tool-failure-recovery-trajectories
- File: `train/recovery_v3.jsonl` (682 OpenAI tool-use trajectories:
  152 tool_success, 480 recovery, 50 no_tool; domains: calendar, email, weather,
  translate, music, flights, stocks, restaurant)
- Failure signals are diverse: `[SOCKET_HANGUP]`, `[REQUEST_TIMEOUT: ...]`,
  `{"error": ..., "code": ...}`, malformed JSON, `null`, `SyntaxError`,
  `response.body is undefined`, and `%%%%PARSE_FAIL%%%%`.

Download and run the end-to-end:

```bash
python scripts/download_recovery_data.py
python scripts/run_real_data.py          # offline mock models
# or, with a real model:
export OPENAI_API_KEY=sk-...
python scripts/run_real_data.py --config configs/production_recovery.yaml
```

Note: email-domain records contain synthetic PII-shaped email addresses in tool
arguments; the quality/redaction layer quarantines these 79/682 records, and
`run_real_data.py` excludes them from benchmark construction.

## AgentTrek

- Source: https://huggingface.co/datasets/xlangai/AgentTrek (Apache-2.0)
- Step-level records (`system` + `user` + `assistant` per record) with browser
  actions embedded as `<action> fn(args) </action>`. No tool-result loop, so it
  supports ACTION-frame decision points only — not the failure behaviors.
