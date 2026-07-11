"""Tests for governance audit logging."""

import json

from app.governance.audit import DEFAULT_AUDIT_PATH, log_event


def test_log_event_appends_to_json_file(tmp_path, monkeypatch):
    audit_file = tmp_path / "audit_log.json"
    monkeypatch.setenv("AUDIT_LOG_PATH", str(audit_file))

    entry = log_event("test_event", {"foo": "bar"}, risk_level="medium")

    assert entry["event_type"] == "test_event"
    assert entry["risk_level"] == "medium"
    assert audit_file.exists()

    events = json.loads(audit_file.read_text(encoding="utf-8"))
    assert len(events) == 1
    assert events[0]["details"]["foo"] == "bar"


def test_log_event_default_path_is_under_data():
    assert DEFAULT_AUDIT_PATH.name == "audit_log.json"
    assert DEFAULT_AUDIT_PATH.parent.name == "data"
