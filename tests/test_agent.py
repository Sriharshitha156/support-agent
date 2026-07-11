"""Tests for the LangGraph support agent."""

import json
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

from app.agent.graph import (
    approve_human_action,
    graph,
    invoke_agent,
    resume_human_gate,
)
from app.governance.audit import DEFAULT_AUDIT_PATH

AUDIT_FILE = DEFAULT_AUDIT_PATH


@pytest.fixture(autouse=True)
def clean_audit_file():
    """Reset audit log file before each test."""
    if AUDIT_FILE.exists():
        AUDIT_FILE.unlink()
    yield
    if AUDIT_FILE.exists():
        AUDIT_FILE.unlink()


def _run(user_message: str, thread_id: str) -> dict:
    return invoke_agent(user_message, thread_id=thread_id)


def test_order_status_runs_lookup_tool():
    result = _run("What is my order status for C1234?", "test-order-status")

    assert result["requires_human_approval"] is False
    assert any(entry["step"] == "preprocess" for entry in result["audit_log"])
    assert any(entry["step"] == "planner" and entry["intent"] == "order_status" for entry in result["audit_log"])
    assert any(entry["step"] == "tool_executor" and entry["action"] == "order_lookup" for entry in result["audit_log"])
    assert any(isinstance(m, AIMessage) and "C1234" in m.content for m in result["messages"])


def test_small_refund_runs_policy_and_refund():
    result = _run("I want a refund of $5 for C1234", "test-small-refund")

    assert result["requires_human_approval"] is False
    assert any(entry["step"] == "tool_executor" and entry["action"] == "refund" for entry in result["audit_log"])


def test_large_refund_triggers_human_gate_with_waiting_approval():
    thread_id = "test-large-refund"
    result = graph.invoke(
        {
            "messages": [HumanMessage(content="Please refund $25 for B9999")],
            "order_id": "",
            "refund_amount": 0.0,
            "requires_human_approval": False,
            "audit_log": [],
        },
        config={"configurable": {"thread_id": thread_id}},
    )

    assert result["requires_human_approval"] is True
    assert result["gate_response"] == {
        "type": "WAITING_APPROVAL",
        "reason": "High value refund or legal threat detected.",
    }
    assert "__interrupt__" in result
    assert any(
        entry.get("action") == "RISK_DETECTED: Escalating to human."
        for entry in result["audit_log"]
    )
    assert not any(entry.get("step") == "tool_executor" for entry in result["audit_log"])

    resumed = resume_human_gate("approve", thread_id=thread_id)

    assert resumed["requires_human_approval"] is False
    assert resumed["approval_status"] == "approved"
    assert any(entry["step"] == "tool_executor" for entry in resumed["audit_log"])


def test_legal_keywords_trigger_human_gate():
    thread_id = "test-legal"
    result = graph.invoke(
        {
            "messages": [HumanMessage(content="I will sue you, give me a refund for A4821")],
            "order_id": "",
            "refund_amount": 0.0,
            "requires_human_approval": False,
            "audit_log": [],
        },
        config={"configurable": {"thread_id": thread_id}},
    )

    assert result["requires_human_approval"] is True
    assert result["gate_response"]["type"] == "WAITING_APPROVAL"
    assert "legal" in result["detected_risk_keywords"] or "sue" in result["detected_risk_keywords"]


def test_reject_ends_with_polite_refusal():
    thread_id = "test-reject"
    graph.invoke(
        {
            "messages": [HumanMessage(content="Refund $50 for B9999")],
            "order_id": "",
            "refund_amount": 0.0,
            "requires_human_approval": False,
            "audit_log": [],
        },
        config={"configurable": {"thread_id": thread_id}},
    )

    result = resume_human_gate("reject", thread_id=thread_id)

    assert result["approval_status"] == "rejected"
    assert any("unable to proceed" in m.content.lower() for m in result["messages"] if isinstance(m, AIMessage))
    assert not any(entry.get("step") == "tool_executor" for entry in result["audit_log"])


def test_apply_refund_not_called_when_human_approval_required():
    state = {
        "messages": [HumanMessage(content="Refund $25 for B9999")],
        "order_id": "B9999",
        "refund_amount": 25.0,
        "requires_human_approval": True,
        "audit_log": [{"step": "planner", "planned_action": "refund"}],
        "gate_response": {
            "type": "WAITING_APPROVAL",
            "reason": "High value refund or legal threat detected.",
        },
    }

    with patch("app.agent.nodes.apply_refund") as mock_refund:
        from app.agent.nodes import tool_executor_node

        result = tool_executor_node(state)

    mock_refund.assert_not_called()
    assert any(entry.get("step") == "tool_executor" and entry.get("action") == "skipped" for entry in result["audit_log"])


def test_approve_human_action_helper():
    state = {
        "messages": [],
        "order_id": "B9999",
        "refund_amount": 25.0,
        "requires_human_approval": True,
        "audit_log": [],
        "gate_response": {
            "type": "WAITING_APPROVAL",
            "reason": "High value refund or legal threat detected.",
        },
    }

    approved = approve_human_action(state, "approve")
    assert approved["requires_human_approval"] is False
    assert approved["approval_status"] == "approved"

    rejected = approve_human_action(state, "reject")
    assert rejected["approval_status"] == "rejected"


def test_audit_log_records_every_step():
    result = _run("Track my order C1234", "test-audit")

    steps = [entry["step"] for entry in result["audit_log"]]
    assert "preprocess" in steps
    assert "planner" in steps
    assert "tool_executor" in steps

    file_events = json.loads(AUDIT_FILE.read_text(encoding="utf-8"))
    assert len(file_events) >= 2


def test_late_order_lookup_mentions_delay():
    result = _run("What is the status of order A4821?", "test-late-order")
    assert any(isinstance(m, AIMessage) and "late" in m.content.lower() for m in result["messages"])
