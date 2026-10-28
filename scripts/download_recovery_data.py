"""Download the public tool-failure-recovery trajectories dataset.

Fetches ``train/recovery_v3.jsonl`` from Hugging Face into ``data/real/`` so
``scripts/run_real_data.py`` can run without manual setup. The dataset is
public; this script never sends private traces anywhere.

Usage: python scripts/download_recovery_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.request import urlopen

URL = "https://huggingface.co/datasets/GurkanOz/tool-failure-recovery-trajectories/resolve/main/train/recovery_v3.jsonl"
DEST = Path(__file__).resolve().parents[1] / "data" / "real" / "recovery_v3.jsonl"


def main() -> None:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {URL}")
    with urlopen(URL, timeout=120) as resp:  # noqa: S310 - public dataset, not user-controlled
        data = resp.read()
    DEST.write_bytes(data)
    lines = data.count(b"\n")
    print(f"wrote {DEST} ({len(data)} bytes, ~{lines} records)")


if __name__ == "__main__":
    sys.exit(main())
