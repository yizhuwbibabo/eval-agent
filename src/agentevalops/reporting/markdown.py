"""Markdown report rendering."""

from __future__ import annotations

from typing import Any


def _pct(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"{v * 100:.1f}%"


def render_markdown(data: dict[str, Any]) -> str:
    s = data["summary"]
    ev = data["evaluation"]
    en = data["engineering"]
    lines: list[str] = []

    lines.append(f"# Agent Failure Analysis Report - {s['run_id']}")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"- Benchmark: {s['benchmark_id']} (dataset version {s['dataset_version']})")
    lines.append(f"- Models under test: {', '.join(s['models'])}")
    lines.append(f"- Total trials: {s['total_trials']}")
    lines.append(
        f"- Valid / invalid / incomplete: {s['valid_trials']} / {s['invalid_trials']} / {s['incomplete_trials']}"
    )
    lines.append(f"- Overall pass rate (micro): {_pct(s['overall_pass_rate'])}")
    lines.append(f"- Macro pass rate: {_pct(ev['macro_pass_rate'])}")
    lines.append(f"- High-risk (unsafe action) failures: {s['high_risk_count']}")
    lines.append("")
    lines.append("Top failure categories:")
    for c in s["top_failure_categories"]:
        lines.append(f"- {c['label']} ({c['count']})")
    lines.append("")
    lines.append("Key recommendations:")
    for r in s["recommendations"]:
        lines.append(f"- {r}")
    lines.append("")

    lines.append("## Agent Behavior Metrics")
    lines.append("")
    lines.append("| Behavior | Pass rate | Failure rate |")
    lines.append("|---|---|---|")
    for b, pr in ev["behavior_pass_rate"].items():
        lines.append(f"| {b} | {_pct(pr)} | {_pct(ev['failure_rate_by_behavior'].get(b))} |")
    lines.append("")
    lines.append("| Model | Pass rate | Completed | Failed (infra) | Unsupported |")
    lines.append("|---|---|---|---|---|")
    for m, mm in ev["by_model"].items():
        lines.append(
            f"| {m} | {_pct(mm['pass_rate'])} | {mm['completed']} | {mm['failed']} | {mm['unsupported']} |"
        )
    lines.append("")

    lines.append("## Engineering Metrics")
    lines.append("")
    lines.append(
        f"- Latency (mean/p50/p95): {_fmt_ms(en['latency_mean_ms'])} / {_fmt_ms(en['latency_p50_ms'])} / {_fmt_ms(en['latency_p95_ms'])}"
    )
    lines.append(f"- Tokens (in/out): {en['input_tokens']} / {en['output_tokens']}")
    lines.append(f"- Estimated cost: ${en['estimated_cost']}")
    lines.append(f"- API error rate: {_pct(en['api_error_rate'])}; timeout rate: {_pct(en['timeout_rate'])}")
    lines.append(f"- Grader failure rate: {_pct(en['grader_failure_rate'])}")
    lines.append("")

    lines.append("## Failure Cases")
    lines.append("")
    if not data["failure_cases"]:
        lines.append("No failures.")
    for _i, case in enumerate(data["failure_cases"], 1):
        lines.append(f"### Case {case['case_id']}")
        lines.append("")
        lines.append(f"- Model: {case['model_id']}")
        lines.append(f"- Benchmark: {case['behavior_name']} ({case['behavior_id']})")
        lines.append(f"- Verdict: {case['verdict']} (score {case['score']})")
        lines.append(f"- Primary failure category: {case['primary_category']}")
        lines.append(f"- Expected: {case['expected']}")
        lines.append(f"- Observed: {case['observed']}")
        lines.append(f"- Root cause confirmable: {case['root_cause_confirmable']}")
        lines.append(f"- Diagnostic boundary: {case['root_cause_note']}")
        lines.append("- Evidence:")
        for e in case["evidence"]:
            lines.append(f"  - [{e['strength']}] {e['statement']}" + (f" (events: {', '.join(e['event_ids'])})" if e.get("event_ids") else ""))
        lines.append("- Recommended action:")
        for r in case["remediation"]:
            lines.append(f"  - [{r['target_module']}] {r['action']}")
        lines.append(f"- Review status: {case['review_status']}")
        lines.append("")

    lines.append("## Notes")
    for n in data["notes"]:
        lines.append(f"- {n}")
    lines.append("")
    return "\n".join(lines)


def _fmt_ms(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"{v:.1f} ms"
