"""Tests for the LangGraph support agent."""

import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

from app.agent.graph import graph, invoke_agent
from app.governance.audit import DEFAULT_AUDIT_PATH, log_event

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
    assert any(entry["step"] == "planner" and entry["intent"] == "order_status" for entry in result["audit_log"])
    assert any(entry["step"] == "tool_executor" and entry["action"] == "order_lookup" for entry in result["audit_log"])
    assert any(isinstance(m, AIMessage) and "C1234" in m.content for m in result["messages"])
    assert AUDIT_FILE.exists()


def test_small_refund_runs_policy_and_refund():
    result = _run("I want a refund of $5 for C1234", "test-small-refund")

    assert result["requires_human_approval"] is False
    assert any(entry["step"] == "tool_executor" and entry["action"] == "refund" for entry in result["audit_log"])


def test_large_refund_triggers_human_gate():
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
    assert "__interrupt__" in result
    assert not any(entry.get("step") == "tool_executor" for entry in result["audit_log"])

    resumed = graph.invoke(
        Command(resume={"approved": True}),
        config={"configurable": {"thread_id": thread_id}},
    )

    assert resumed["requires_human_approval"] is False
    assert any(entry["step"] == "tool_executor" for entry in resumed["audit_log"])


def test_escalation_language_blocks_refund_tool():
    thread_id = "test-escalation"
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
    assert "__interrupt__" in result
    interrupt_payload = result["__interrupt__"][0].value
    assert "ACTION_REQUIRED" in interrupt_payload["message"]
    assert "escalation language" in interrupt_payload["reason"]


def test_audit_log_records_every_step():
    result = _run("Track my order C1234", "test-audit")

    steps = [entry["step"] for entry in result["audit_log"]]
    assert "planner" in steps
    assert "tool_executor" in steps
    assert all("timestamp" in entry for entry in result["audit_log"])

    file_events = json.loads(AUDIT_FILE.read_text(encoding="utf-8"))
    assert len(file_events) >= 2
    assert all("event_type" in event for event in file_events)


def test_late_order_lookup_mentions_delay():
    result = _run("What is the status of order A4821?", "test-late-order")
    assert any(isinstance(m, AIMessage) and "late" in m.content.lower() for m in result["messages"])
