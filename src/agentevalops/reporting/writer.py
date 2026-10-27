"""Report artifact writer.

Writes the report bundle for a run under ``reports/<run_id>/``:
summary.md, detailed_report.html, metrics.json, failure_cases.jsonl,
model_comparison.csv and (optionally) regression_report.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from agentevalops.reporting.comparison import model_comparison_rows, render_comparison_csv
from agentevalops.reporting.data import RunArtifacts, assemble_report_data
from agentevalops.reporting.html import render_html
from agentevalops.reporting.json_report import render_metrics_json
from agentevalops.reporting.markdown import render_markdown


def write_report(artifacts: RunArtifacts, output_dir: str | Path) -> dict[str, str]:
    data = assemble_report_data(artifacts)
    rows = model_comparison_rows(artifacts)

    run_dir = Path(output_dir) / artifacts.run.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, str] = {}

    summary_path = run_dir / "summary.md"
    summary_path.write_text(render_markdown(data), encoding="utf-8")
    paths["summary"] = str(summary_path)

    html_path = run_dir / "detailed_report.html"
    html_path.write_text(render_html(data, rows), encoding="utf-8")
    paths["html"] = str(html_path)

    metrics_path = run_dir / "metrics.json"
    metrics_path.write_text(json.dumps(render_metrics_json(data), indent=2, default=str), encoding="utf-8")
    paths["metrics"] = str(metrics_path)

    failure_path = run_dir / "failure_cases.jsonl"
    with failure_path.open("w", encoding="utf-8") as f:
        for case in data["failure_cases"]:
            f.write(json.dumps(case, default=str) + "\n")
    paths["failure_cases"] = str(failure_path)

    csv_path = run_dir / "model_comparison.csv"
    csv_path.write_text(render_comparison_csv(rows), encoding="utf-8")
    paths["model_comparison"] = str(csv_path)

    return paths
