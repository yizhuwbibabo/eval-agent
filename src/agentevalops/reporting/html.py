"""Self-contained HTML report rendering (inline CSS, no external assets)."""

from __future__ import annotations

import html as _html
from typing import Any


def _esc(v: Any) -> str:
    return _html.escape(str(v))


def _pct(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"{v * 100:.1f}%"


def render_html(data: dict[str, Any], comparison_rows: list[dict[str, Any]] | None = None) -> str:
    s = data["summary"]
    ev = data["evaluation"]
    en = data["engineering"]
    comparison_rows = comparison_rows or []

    parts: list[str] = []
    parts.append(
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<title>Agent Failure Analysis Report</title>"
        "<style>"
        "body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;"
        "margin:2rem auto;max-width:960px;padding:0 1rem;color:#1a1a1a;line-height:1.5;}"
        "h1{font-size:1.7rem;border-bottom:2px solid #ddd;padding-bottom:.4rem;}"
        "h2{font-size:1.25rem;margin-top:2rem;border-bottom:1px solid #eee;padding-bottom:.3rem;}"
        "h3{font-size:1.05rem;}"
        "table{border-collapse:collapse;width:100%;margin:.6rem 0;font-size:.9rem;}"
        "th,td{border:1px solid #ccc;padding:.35rem .5rem;text-align:left;vertical-align:top;}"
        "th{background:#f2f2f2;}"
        ".kpi{display:flex;flex-wrap:wrap;gap:.6rem;margin:.8rem 0;}"
        ".kpi div{flex:1 1 160px;border:1px solid #ddd;border-radius:6px;padding:.6rem;background:#fafafa;}"
        ".kpi .v{font-size:1.4rem;font-weight:600;}"
        ".badge-fail{color:#b00020;font-weight:600;}"
        ".badge-pass{color:#1b5e20;font-weight:600;}"
        ".case{border:1px solid #ddd;border-radius:6px;padding:.8rem;margin:.8rem 0;background:#fff;}"
        ".ev{margin:.2rem 0;font-size:.85rem;color:#444;}"
        ".note{color:#666;font-size:.85rem;}"
        "code{background:#f4f4f4;padding:.1rem .3rem;border-radius:3px;}"
        "</style></head><body>"
    )

    parts.append("<h1>Agent Failure Analysis Report</h1>")
    parts.append(f"<p class='note'>Run <code>{_esc(s['run_id'])}</code> · Benchmark {_esc(s['benchmark_id'])} v{_esc(s['dataset_version'])}</p>")

    parts.append("<h2>Executive Summary</h2>")
    parts.append("<div class='kpi'>")
    parts.append(f"<div><div class='v'>{_esc(s['total_trials'])}</div>total trials</div>")
    parts.append(f"<div><div class='v'>{_esc(s['valid_trials'])}</div>valid</div>")
    parts.append(f"<div><div class='v'>{_esc(s['incomplete_trials'])}</div>incomplete</div>")
    parts.append(f"<div><div class='v'>{_pct(s['overall_pass_rate'])}</div>overall pass</div>")
    parts.append(f"<div><div class='v'>{_esc(s['high_risk_count'])}</div>high-risk failures</div>")
    parts.append("</div>")
    parts.append(f"<p>Models: {', '.join(_esc(m) for m in s['models'])}</p>")

    parts.append("<h3>Top failure categories</h3><ul>")
    for c in s["top_failure_categories"]:
        parts.append(f"<li>{_esc(c['label'])} — {c['count']}</li>")
    parts.append("</ul>")

    parts.append("<h3>Recommendations</h3><ul>")
    for r in s["recommendations"]:
        parts.append(f"<li>{_esc(r)}</li>")
    parts.append("</ul>")

    parts.append("<h2>Agent Behavior Metrics</h2>")
    parts.append("<table><tr><th>Behavior</th><th>Pass rate</th><th>Failure rate</th></tr>")
    for b, pr in ev["behavior_pass_rate"].items():
        parts.append(
            f"<tr><td>{_esc(b)}</td><td>{_pct(pr)}</td><td>{_pct(ev['failure_rate_by_behavior'].get(b))}</td></tr>"
        )
    parts.append("</table>")

    parts.append("<h2>Model Comparison</h2>")
    if comparison_rows:
        parts.append("<table><tr><th>Model</th><th>Pass rate</th><th>Latency (ms)</th>"
                     "<th>Tokens in</th><th>Tokens out</th><th>Cost</th><th>API error</th></tr>")
        for r in comparison_rows:
            parts.append(
                f"<tr><td>{_esc(r['model_id'])}</td><td>{_pct(r['pass_rate'])}</td>"
                f"<td>{_esc(round(r['latency_mean_ms'],1) if r['latency_mean_ms'] is not None else 'n/a')}</td>"
                f"<td>{_esc(r['input_tokens'])}</td><td>{_esc(r['output_tokens'])}</td>"
                f"<td>{_esc(r['estimated_cost'])}</td><td>{_pct(r['api_error_rate'])}</td></tr>"
            )
        parts.append("</table>")
    else:
        parts.append("<p class='note'>No model comparison available.</p>")

    parts.append("<h2>Engineering Metrics</h2>")
    parts.append(
        f"<p>Latency mean/p50/p95: {_esc(en['latency_mean_ms'])} / {_esc(en['latency_p50_ms'])} / {_esc(en['latency_p95_ms'])} ms</p>"
    )
    parts.append(
        f"<p>Tokens in/out: {_esc(en['input_tokens'])} / {_esc(en['output_tokens'])} · "
        f"estimated cost ${_esc(en['estimated_cost'])} · API error rate {_pct(en['api_error_rate'])} · "
        f"grader failure rate {_pct(en['grader_failure_rate'])}</p>"
    )

    parts.append("<h2>Failure Cases</h2>")
    if not data["failure_cases"]:
        parts.append("<p>No failures.</p>")
    for case in data["failure_cases"]:
        verdict_cls = "badge-fail" if case["verdict"] == "FAIL" else "badge-pass"
        parts.append("<div class='case'>")
        parts.append(f"<h3>{_esc(case['case_id'])} <span class='{verdict_cls}'>{_esc(case['verdict'])}</span></h3>")
        parts.append(f"<p><strong>Model:</strong> {_esc(case['model_id'])} · "
                     f"<strong>Behavior:</strong> {_esc(case['behavior_name'])} · "
                     f"<strong>Category:</strong> {_esc(case['primary_category'])} · "
                     f"<strong>Score:</strong> {_esc(case['score'])}</p>")
        parts.append(f"<p><strong>Expected:</strong> {_esc(case['expected'])}</p>")
        parts.append(f"<p><strong>Observed:</strong> {_esc(case['observed'])}</p>")
        parts.append("<p><strong>Evidence:</strong></p>")
        for e in case["evidence"]:
            ev_ids = f" (events: {', '.join(e['event_ids'])})" if e.get("event_ids") else ""
            parts.append(f"<div class='ev'>[{_esc(e['strength'])}] {_esc(e['statement'])}{_esc(ev_ids)}</div>")
        parts.append(f"<p><strong>Diagnostic boundary:</strong> {_esc(case['root_cause_note'])}</p>")
        parts.append("<p><strong>Recommended action:</strong></p><ul>")
        for r in case["remediation"]:
            parts.append(f"<li>[{_esc(r['target_module'])}] {_esc(r['action'])}</li>")
        parts.append("</ul>")
        parts.append(f"<p class='note'>Review status: {_esc(case['review_status'])}</p>")
        parts.append("</div>")

    parts.append("<h2>Notes</h2><ul>")
    for n in data["notes"]:
        parts.append(f"<li class='note'>{_esc(n)}</li>")
    parts.append("</ul>")
    parts.append("</body></html>")
    return "\n".join(parts)
