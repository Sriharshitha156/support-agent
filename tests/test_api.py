"""Tests for FastAPI endpoints."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.governance.audit import DEFAULT_AUDIT_PATH
from app.main import app

client = TestClient(app)
AUDIT_FILE = DEFAULT_AUDIT_PATH


@pytest.fixture(autouse=True)
def clean_audit_file():
    if AUDIT_FILE.exists():
        AUDIT_FILE.unlink()
    yield
    if AUDIT_FILE.exists():
        AUDIT_FILE.unlink()


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_order_status():
    session_id = f"api-{uuid.uuid4()}"
    response = client.post(
        "/chat",
        json={"message": "What is the status of order C1234?", "session_id": session_id},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "complete"
    assert "C1234" in payload["response"]


def test_chat_high_value_refund_waits_for_approval():
    session_id = f"api-{uuid.uuid4()}"
    response = client.post(
        "/chat",
        json={"message": "Refund $25 for B9999", "session_id": session_id},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "WAITING_APPROVAL"
    assert payload["gate_response"]["type"] == "WAITING_APPROVAL"


def test_approve_endpoint_resumes_flow():
    session_id = f"api-{uuid.uuid4()}"
    client.post("/chat", json={"message": "Refund $25 for B9999", "session_id": session_id})

    response = client.post(
        "/approve",
        json={"session_id": session_id, "decision": "approve"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "complete"
    assert payload["approval_status"] == "approved"


def test_reject_endpoint_ends_with_refusal():
    session_id = f"api-{uuid.uuid4()}"
    client.post("/chat", json={"message": "Refund $25 for B9999", "session_id": session_id})

    response = client.post(
        "/approve",
        json={"session_id": session_id, "decision": "reject"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["approval_status"] == "rejected"
    assert "unable to proceed" in payload["response"].lower()


def test_get_audit_log_returns_recent_events():
    session_id = f"api-{uuid.uuid4()}"
    client.post("/chat", json={"message": "Track order C1234", "session_id": session_id})

    response = client.get("/get_audit_log")
    assert response.status_code == 200
    events = response.json()["events"]
    assert isinstance(events, list)
    assert len(events) >= 1
    assert len(events) <= 10
