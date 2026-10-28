"""Audit trail tests."""

from __future__ import annotations

import json

from agentevalops.observability.audit import audit_external_call


def test_audit_writes_jsonl(tmp_path) -> None:
    path = str(tmp_path / "audit.jsonl")
    audit_external_call(path, provider="openai_compat", model="deepseek-flash", instance_id="i1")
    audit_external_call(path, provider="judge", model="glm-5", instance_id="i2")
    lines = (tmp_path / "audit.jsonl").read_text().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["event"] == "external_model_call"
    assert first["provider"] == "openai_compat"
    assert first["instance_id"] == "i1"
    assert "timestamp" in first


def test_audit_noop_without_path() -> None:
    # Must not raise and must not write anything.
    audit_external_call(None, provider="openai_compat", model="m")
