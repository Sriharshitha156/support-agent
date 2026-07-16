"""
LangGraph graph definition and compilation.

Exports a compiled `graph` with checkpointer for session persistence.

Flow: Request -> Preprocess -> Planner -> [Human Gate | Tool Executor]
      Human Gate -> Wait -> Approve/Reject -> [Tool Executor | End]
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command

from app.agent.state import AgentState
from app.agent.nodes import (
    PLANNED_ACTION_KEY,
    preprocess_node,
    planner_node,
    human_gate_node,
    tool_executor_node,
    approve_human_action,
    _get_planner_context,
    _waiting_approval_payload,
    _normalize_approval_decision,
)

# Re-export nodes for external tests that import them directly from graph.py
__all__ = [
    "graph",
    "preprocess_node",
    "planner_node",
    "human_gate_node",
    "tool_executor_node",
    "approve_human_action",
    "invoke_agent",
    "resume_human_gate",
    "resume_agent",
    "format_agent_result",
]

# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def route_after_planner(state: AgentState) -> str:
    if state.get("requires_human_approval"):
        return "human_gate"
    planner_ctx = _get_planner_context(state)
    if planner_ctx.get(PLANNED_ACTION_KEY) in (
        "order_lookup",
        "policy_check",
        "refund",
        "refuse_out_of_scope",
        "general_inquiry",
    ):
        return "tool_executor"
    return END


def route_after_human_gate(state: AgentState) -> str:
    if state.get("approval_status") == "rejected":
        return END
    if state.get("requires_human_approval"):
        return END
    planner_ctx = _get_planner_context(state)
    if planner_ctx.get(PLANNED_ACTION_KEY) in (
        "order_lookup",
        "policy_check",
        "refund",
        "refuse_out_of_scope",
        "general_inquiry",
    ):
        return "tool_executor"
    return END


# ---------------------------------------------------------------------------
# Graph compilation
# ---------------------------------------------------------------------------


def build_graph():
    """Compile the support agent graph with an in-memory checkpointer."""
    workflow = StateGraph(AgentState)

    workflow.add_node("preprocess", preprocess_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("human_gate", human_gate_node)
    workflow.add_node("tool_executor", tool_executor_node)

    workflow.set_entry_point("preprocess")
    workflow.add_edge("preprocess", "planner")

    workflow.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "human_gate": "human_gate",
            "tool_executor": "tool_executor",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "human_gate",
        route_after_human_gate,
        {
            "tool_executor": "tool_executor",
            END: END,
        },
    )

    workflow.add_edge("tool_executor", END)

    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


graph = build_graph()


def invoke_agent(
    user_message: str,
    *,
    thread_id: str = "default",
    order_id: str = "",
    refund_amount: float = 0.0,
) -> dict:
    """Run the graph for a single user turn."""
    config = {"configurable": {"thread_id": thread_id}}
    initial_state: AgentState = {
        "messages": [HumanMessage(content=user_message)],
        "order_id": order_id,
        "refund_amount": refund_amount,
        "requires_human_approval": False,
        "audit_log": [],
    }
    return graph.invoke(initial_state, config=config)


def resume_human_gate(approval_decision: str, *, thread_id: str = "default") -> dict:
    """Resume a paused human gate with an explicit approve/reject decision."""
    decision = approval_decision.strip().lower()
    if decision not in ("approve", "reject"):
        raise ValueError("approval_decision must be 'approve' or 'reject'")
    config = {"configurable": {"thread_id": thread_id}}
    return graph.invoke(Command(resume={"decision": decision}), config=config)


def resume_agent(human_decision: dict | bool | str, *, thread_id: str = "default") -> dict:
    """Backward-compatible resume helper."""
    if isinstance(human_decision, str):
        return resume_human_gate(human_decision, thread_id=thread_id)
    if isinstance(human_decision, dict) and "decision" in human_decision:
        return resume_human_gate(str(human_decision["decision"]), thread_id=thread_id)
    normalized = "approve" if human_decision else "reject"
    return resume_human_gate(normalized, thread_id=thread_id)


def format_agent_result(state: dict) -> dict:
    """Normalize graph state into a stable API/UI payload."""
    gate_response = dict(state.get("gate_response") or {})
    if "__interrupt__" in state and state["__interrupt__"]:
        interrupt_value = state["__interrupt__"][0].value
        if isinstance(interrupt_value, dict):
            gate_response = interrupt_value

    approval_status = state.get("approval_status", "")
    waiting = approval_status not in ("approved", "rejected") and (
        gate_response.get("type") == "WAITING_APPROVAL"
        or (state.get("requires_human_approval") and "__interrupt__" in state)
    )

    response_text = ""
    for message in reversed(state.get("messages", [])):
        if isinstance(message, AIMessage):
            response_text = message.content if isinstance(message.content, str) else str(message.content)
            break

    if waiting and not response_text:
        reason = gate_response.get("reason", "High value refund or legal threat detected.")
        response_text = f"WAITING_APPROVAL: {reason}"

    return {
        "status": "WAITING_APPROVAL" if waiting else "complete",
        "response": response_text,
        "gate_response": gate_response,
        "requires_human_approval": bool(state.get("requires_human_approval")),
        "approval_status": state.get("approval_status", ""),
        "audit_log": state.get("audit_log", []),
    }
