"""JSON report rendering."""

from __future__ import annotations

from typing import Any


def render_metrics_json(data: dict[str, Any]) -> dict[str, Any]:
    """The metrics.json artifact is the full assembled report document."""
    return data
