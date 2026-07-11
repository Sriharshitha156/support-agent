"""Tests for the LangGraph support agent."""

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

from app.agent.graph import graph, invoke_agent


def _run(user_message: str, thread_id: str) -> dict:
    return invoke_agent(user_message, thread_id=thread_id)


def test_order_status_runs_lookup_tool():
    result = _run("What is my order status for ORD-1001?", "test-order-status")

    assert result["requires_human_approval"] is False
    assert any(entry["step"] == "planner" and entry["intent"] == "order_status" for entry in result["audit_log"])
    assert any(entry["step"] == "tool_executor" and entry["action"] == "order_lookup" for entry in result["audit_log"])
    assert any(isinstance(m, AIMessage) and "ORD-1001" in m.content for m in result["messages"])


def test_small_refund_runs_policy_check():
    result = _run("I want a refund of $5 for ORD-1001", "test-small-refund")

    assert result["requires_human_approval"] is False
    assert any(entry["step"] == "tool_executor" and entry["action"] == "policy_check" for entry in result["audit_log"])


def test_large_refund_triggers_human_gate():
    thread_id = "test-large-refund"
    result = graph.invoke(
        {
            "messages": [HumanMessage(content="Please refund $25 for ORD-1001")],
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
            "messages": [HumanMessage(content="I will sue you, give me a refund for ORD-1001")],
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
    result = _run("Track my order ORD-1002", "test-audit")

    steps = [entry["step"] for entry in result["audit_log"]]
    assert "planner" in steps
    assert "tool_executor" in steps
    assert all("timestamp" in entry for entry in result["audit_log"])
