"""Append-only audit trail for external model calls.

Every time trace content is sent to an external model (model-under-test or
judge), a structured JSON record is appended to the configured audit log. This
is the compliance trail: it records *which* trace content was sent *where* and
*when*, without logging the payload or any secret.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

_lock = threading.Lock()


def audit_external_call(path: str | None, **fields: Any) -> None:
    """Append one audit record. No-op when no path is configured."""
    if not path:
        return
    record = dict(fields)
    record["event"] = "external_model_call"
    record["timestamp"] = time.time()
    line = json.dumps(record, default=str)
    with _lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
