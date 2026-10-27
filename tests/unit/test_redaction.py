"""Redaction tests."""

from __future__ import annotations

from agentevalops.redaction import Redactor, default_redactor
from agentevalops.schemas.trace import Trace, TraceEvent, TraceEventType


def test_redact_api_key() -> None:
    r = Redactor()
    out, hits = r.redact_string("api_key=sk-abcdef123456")
    assert "sk-abcdef123456" not in out
    assert "api_key" in hits or "secret_key" in hits


def test_redact_sk_secret() -> None:
    r = default_redactor()
    out, hits = r.redact_string("key is sk-abcdef1234567890")
    assert "sk-abcdef1234567890" not in out
    assert "secret_key" in hits


def test_redact_email_and_ip() -> None:
    r = default_redactor()
    out, hits = r.redact_string("contact a@b.com at 10.0.0.1")
    assert "a@b.com" not in out
    assert "10.0.0.1" not in out
    assert "email" in hits
    assert "ip_address" in hits


def test_redact_trace_preserves_structure() -> None:
    r = default_redactor()
    trace = Trace(
        trace_id="t",
        source_system="x",
        dataset_source="synthetic",
        events=[
            TraceEvent(
                event_id="e1",
                event_type=TraceEventType.USER,
                content="token sk-abcdef1234567890",
                tool_arguments={"auth": "api_key=secret12345678"},
            )
        ],
    )
    redacted, hits = r.redact_trace(trace)
    assert redacted.trace_id == "t"
    assert "sk-abcdef1234567890" not in redacted.events[0].content
    assert "secret12345678" not in str(redacted.events[0].tool_arguments)
    assert hits


def test_scan_event_detects_secret() -> None:
    r = default_redactor()
    ev = TraceEvent(event_id="e1", event_type=TraceEventType.USER, content="Bearer abcdef1234567890")
    hits = r.scan_event(ev)
    assert any(h.rule == "bearer_token" for h in hits)
