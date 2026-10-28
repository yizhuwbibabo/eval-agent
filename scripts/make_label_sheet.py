"""Render labels.jsonl into a readable review sheet + a blank answer file.

Usage:
    python scripts/make_label_sheet.py [labels.jsonl]

Produces (in the current directory):
    label_sheet.md     — human-readable cards, one per case (read-only reference)
    label_answers.txt  — one line per row: "<index>\\t" — fill in true/false

After filling label_answers.txt, fold the answers back with:
    python scripts/apply_labels.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _fmt_obj(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("labels.jsonl")
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    cards: list[str] = []
    answers: list[str] = []
    for i, r in enumerate(rows, 1):
        cards.append(f"\n## 案例 {i}\n")
        cards.append(f"- trial_id: `{r['trial_id']}`")
        cards.append(f"- instance_id: `{r['instance_id']}`")
        cards.append(f"- grader_passed: {r['grader_passed']}  （仅供参考，独立判断，不要照抄）")
        cards.append(f"- grader_score: {r['grader_score']}\n")

        cards.append("### 上下文（工具失败经过）\n")
        for m in r["context"]:
            role = m.get("role") or "?"
            if m.get("tool_name"):
                args = _fmt_obj(m.get("tool_arguments") or {})
                cards.append(f"- [{role}] 工具调用 `{m['tool_name']}` 参数：\n```\n{args}\n```")
            content = m.get("content") or ""
            if content:
                cards.append(f"- [{role}] {content}")
            if m.get("tool_result") is not None:
                cards.append(f"  → 工具返回：{m.get('tool_result')}")
            if m.get("error"):
                cards.append(f"  → 错误：{m.get('error')}")

        cards.append("\n### 模型回应\n")
        mr = r["model_response"]
        if mr.get("text"):
            cards.append(f"- 文本：{mr['text']}")
        for tc in mr.get("tool_calls") or []:
            args = _fmt_obj(tc.get("arguments") or {})
            cards.append(f"- 工具调用 `{tc['name']}` 参数：\n```\n{args}\n```")
        if mr.get("error"):
            cards.append(f"- 错误：{mr['error']}")
        cards.append("")

        answers.append(f"{i}\t")

    Path("label_sheet.md").write_text("\n".join(cards), encoding="utf-8")
    Path("label_answers.txt").write_text("\n".join(answers) + "\n", encoding="utf-8")
    print(f"wrote label_sheet.md and label_answers.txt ({len(rows)} rows)")
    print("fill each line of label_answers.txt with 'true' or 'false' after the tab")


if __name__ == "__main__":
    main()
