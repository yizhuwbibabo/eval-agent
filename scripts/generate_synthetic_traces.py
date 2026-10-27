"""Generate the synthetic trace dataset.

Outputs datasets/synthetic/traces.jsonl. All traces are clearly marked
``dataset_source="synthetic"``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agentevalops.datagen import generate_all, write_dataset  # noqa: E402


def main() -> None:
    traces = generate_all()
    out = Path("datasets/synthetic/traces.jsonl")
    write_dataset(traces, out)
    print(f"wrote {len(traces)} synthetic traces to {out}")


if __name__ == "__main__":
    main()
