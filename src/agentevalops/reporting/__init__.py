"""Reporting layer."""

from agentevalops.reporting.comparison import model_comparison_rows, render_comparison_csv
from agentevalops.reporting.data import RunArtifacts, assemble_report_data
from agentevalops.reporting.html import render_html
from agentevalops.reporting.json_report import render_metrics_json
from agentevalops.reporting.markdown import render_markdown
from agentevalops.reporting.regression import compare_runs
from agentevalops.reporting.writer import write_report

__all__ = [
    "RunArtifacts",
    "assemble_report_data",
    "compare_runs",
    "model_comparison_rows",
    "render_comparison_csv",
    "render_html",
    "render_metrics_json",
    "render_markdown",
    "write_report",
]
