"""Fold filled label_answers.txt back into labels.jsonl.

Usage:
    python scripts/apply_labels.py [labels.jsonl] [label_answers.txt]

Reads each answer line of the form "<index> true|false", validates that every
row got exactly one answer in order, then writes the labels back into
labels.jsonl (one JSON object per line, as ingest-labels expects).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    labels_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("labels.jsonl")
    answers_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("label_answers.txt")

    rows = [
        json.loads(line)
        for line in labels_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    answers: list[tuple[int, bool]] = []
    for line in answers_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            raise SystemExit(f"bad answer line: {line!r} (expected '<index> true|false')")
        idx, val = parts
        if val not in ("true", "false"):
            raise SystemExit(f"bad value {val!r} on line {idx}; use true/false")
        answers.append((int(idx), val == "true"))

    if len(answers) != len(rows):
        raise SystemExit(f"expected {len(rows)} answers, got {len(answers)}")

    for i, (idx, val) in enumerate(answers):
        if idx != i + 1:
            raise SystemExit(f"answer line {i + 1} has index {idx}; expected {i + 1}")
        rows[i]["label"] = val

    labels_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    n_true = sum(1 for r in rows if r["label"] is True)
    print(f"wrote {len(rows)} labels to {labels_path} ({n_true} true, {len(rows) - n_true} false)")


if __name__ == "__main__":
    main()
