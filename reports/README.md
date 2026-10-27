# Generated reports

This directory holds generated Agent Failure Analysis Report bundles, one
subdirectory per run.

To regenerate the offline example:

```bash
python scripts/generate_synthetic_traces.py
python scripts/run_e2e.py --config configs/development.yaml
```

The bundle for `e2e_run` contains:

- `summary.md` — executive summary
- `detailed_report.html` — self-contained detailed report
- `metrics.json` — structured metrics
- `failure_cases.jsonl` — machine-readable failure records
- `model_comparison.csv` — paired model comparison
