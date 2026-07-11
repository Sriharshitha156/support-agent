"""Tests for governance audit logging and response compliance refusal."""

from __future__ import annotations

import json

from app.governance.audit import DEFAULT_AUDIT_PATH, log_event
from app.governance.refusal import check_pii_exposure, verify_compliance


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


# --- Response Refusal & Compliance Tests ---

def test_check_pii_exposure():
    # Card number check
    assert check_pii_exposure("Your card 1234567812345678 has been refunded.") is True
    assert check_pii_exposure("Your card ending in 4321 has been refunded.") is False

    # Other order leakage check
    assert check_pii_exposure("Here is details of order ORD-9999.", allowed_order_id="ORD-1001") is True
    assert check_pii_exposure("Here is details of order ORD-1001.", allowed_order_id="ORD-1001") is False
    assert check_pii_exposure("Here is details of order ORD-1001.", allowed_order_id=None) is False


def test_verify_compliance_pii_refused():
    state = {"order_id": "ORD-1001"}
    res = verify_compliance("Refunding card 1111222233334444.", state)
    assert res["compliant"] is False
    assert res["action"] == "refuse"
    assert "PII leakage" in res["reason"]


def test_verify_compliance_unauthorized_refund_escalated():
    # Attempting to promise refund without manager approval when amount > $10
    state = {
        "order_id": "ORD-1001",
        "refund_amount": 25.0,
        "requires_human_approval": True,
        "approval_status": ""
    }
    res = verify_compliance("Your refund processed successfully.", state)
    assert res["compliant"] is False
    assert res["action"] == "escalate"
    assert "awaiting manager review" in res["modified_text"]


def test_verify_compliance_approved_refund_allowed():
    state = {
        "order_id": "ORD-1001",
        "refund_amount": 25.0,
        "requires_human_approval": False,
        "approval_status": "approved"
    }
    res = verify_compliance("Your refund approved successfully.", state)
    assert res["compliant"] is True
    assert res["action"] == "allow"
