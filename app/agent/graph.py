"""
LangGraph graph definition and compilation.

Exports a compiled `graph` with checkpointer for session persistence.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from app.agent.state import AgentState

# ---------------------------------------------------------------------------
# Constants & routing labels
# ---------------------------------------------------------------------------

PlannedAction = Literal["none", "order_lookup", "policy_check", "refund"]
ESCALATION_KEYWORDS = ("sue", "lawyer", "complaint")
REFUND_KEYWORDS = ("refund", "return")
ORDER_STATUS_KEYWORDS = ("order status", "track my order", "where is my order", "shipping status", "track order")
REFUND_THRESHOLD_USD = 10.0

# Stored on the last planner audit entry for downstream routing.
PLANNED_ACTION_KEY = "planned_action"
APPROVAL_REASON_KEY = "approval_reason"


# ---------------------------------------------------------------------------
# Audit helper
# ---------------------------------------------------------------------------


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_audit(audit_log: list[dict], entry: dict) -> list[dict]:
    return audit_log + [{**entry, "timestamp": _utcnow()}]


def _latest_user_text(state: AgentState) -> str:
    for message in reversed(state["messages"]):
        if isinstance(message, HumanMessage):
            return message.content if isinstance(message.content, str) else str(message.content)
    return ""


def _extract_order_id(text: str) -> str:
    match = re.search(r"ORD-\d+", text, re.IGNORECASE)
    return match.group(0).upper() if match else ""


def _extract_refund_amount(text: str) -> float:
    dollar_match = re.search(r"\$\s*(\d+(?:\.\d{1,2})?)", text)
    if dollar_match:
        return float(dollar_match.group(1))

    amount_match = re.search(
        r"(\d+(?:\.\d{1,2})?)\s*(?:dollars?|usd|bucks)\b", text, re.IGNORECASE
    )
    if amount_match:
        return float(amount_match.group(1))

    return 0.0


def _detect_intent(text: str) -> str:
    lowered = text.lower()
    if any(keyword in lowered for keyword in ORDER_STATUS_KEYWORDS) or "status" in lowered:
        return "order_status"
    if any(keyword in lowered for keyword in REFUND_KEYWORDS):
        return "refund"
    return "general"


def _get_planner_context(state: AgentState) -> dict:
    for entry in reversed(state["audit_log"]):
        if entry.get("step") == "planner":
            return entry
    return {}


# ---------------------------------------------------------------------------
# Mock tools (real implementations come in app/tools/)
# ---------------------------------------------------------------------------


def mock_order_lookup(order_id: str) -> dict:
    """Simulate order status lookup."""
    return {
        "order_id": order_id or "ORD-UNKNOWN",
        "status": "delivered",
        "carrier": "MockShip",
        "eta": "2026-07-05",
        "message": f"Order {order_id} was delivered on 2026-07-05.",
    }


def mock_policy_check(order_id: str, refund_amount: float) -> dict:
    """Simulate refund policy evaluation."""
    eligible = refund_amount <= 500.0
    return {
        "order_id": order_id or "ORD-UNKNOWN",
        "refund_amount": refund_amount,
        "eligible": eligible,
        "policy": "30-day return window",
        "message": (
            f"Refund of ${refund_amount:.2f} is within policy."
            if eligible
            else f"Refund of ${refund_amount:.2f} exceeds automated policy limits."
        ),
    }


def mock_refund_tool(order_id: str, refund_amount: float) -> dict:
    """Simulate refund processing."""
    return {
        "order_id": order_id or "ORD-UNKNOWN",
        "refund_amount": refund_amount,
        "confirmation_id": "RFND-MOCK-001",
        "status": "approved",
        "message": f"Refund of ${refund_amount:.2f} initiated for {order_id}.",
    }


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def planner_node(state: AgentState) -> dict:
    """
    Analyze the latest user message, classify intent, and decide next action.

    Sets requires_human_approval when refund > $10 or escalation language is detected.
    """
    user_text = _latest_user_text(state)
    intent = _detect_intent(user_text)
    order_id = state.get("order_id") or _extract_order_id(user_text)
    refund_amount = state.get("refund_amount") or _extract_refund_amount(user_text)

    planned_action: PlannedAction = "none"
    requires_human_approval = False
    approval_reason = ""

    escalation_hit = next((kw for kw in ESCALATION_KEYWORDS if kw in user_text.lower()), None)

    if intent == "order_status":
        planned_action = "order_lookup"
    elif intent == "refund":
        planned_action = "policy_check"
        if escalation_hit:
            requires_human_approval = True
            approval_reason = f"escalation language detected ('{escalation_hit}')"
            planned_action = "refund"
        elif refund_amount > REFUND_THRESHOLD_USD:
            requires_human_approval = True
            approval_reason = f"refund amount ${refund_amount:.2f} exceeds ${REFUND_THRESHOLD_USD:.2f} threshold"

    audit_entry = {
        "step": "planner",
        "action": "intent_detection",
        "intent": intent,
        PLANNED_ACTION_KEY: planned_action,
        "order_id": order_id,
        "refund_amount": refund_amount,
        "requires_human_approval": requires_human_approval,
        APPROVAL_REASON_KEY: approval_reason,
        "user_text_excerpt": user_text[:200],
    }

    return {
        "order_id": order_id,
        "refund_amount": refund_amount,
        "requires_human_approval": requires_human_approval,
        "audit_log": _append_audit(state.get("audit_log", []), audit_entry),
    }


def human_gate_node(state: AgentState) -> dict:
    """
    Pause for human approval when required.

    Emits ACTION_REQUIRED message and interrupts until a human resumes with a decision.
    """
    planner_ctx = _get_planner_context(state)
    reason = planner_ctx.get(APPROVAL_REASON_KEY) or "high-risk request"
    pause_message = f"ACTION_REQUIRED: Human approval needed for {reason}. Waiting for input."

    audit_log = _append_audit(
        state.get("audit_log", []),
        {
            "step": "human_gate",
            "action": "pause",
            "reason": reason,
            "message": pause_message,
        },
    )

    human_decision = interrupt(
        {
            "type": "human_approval",
            "reason": reason,
            "message": pause_message,
        }
    )

    approved = False
    if isinstance(human_decision, dict):
        approved = bool(human_decision.get("approved", False))
    elif isinstance(human_decision, bool):
        approved = human_decision

    resolution_message = (
        "Human approval granted. Proceeding with requested action."
        if approved
        else pause_message
    )

    return {
        "messages": [AIMessage(content=resolution_message)],
        "requires_human_approval": not approved,
        "audit_log": _append_audit(
            audit_log,
            {
                "step": "human_gate",
                "action": "resume",
                "approved": approved,
                "human_decision": human_decision,
            },
        ),
    }


def tool_executor_node(state: AgentState) -> dict:
    """
    Execute mock tools when human approval is not required or has been granted.
    """
    if state.get("requires_human_approval"):
        audit_entry = {
            "step": "tool_executor",
            "action": "skipped",
            "reason": "human approval still required",
        }
        return {
            "messages": [AIMessage(content="Tool execution blocked: awaiting human approval.")],
            "audit_log": _append_audit(state.get("audit_log", []), audit_entry),
        }

    planner_ctx = _get_planner_context(state)
    planned_action: PlannedAction = planner_ctx.get(PLANNED_ACTION_KEY, "none")
    order_id = state.get("order_id", "")
    refund_amount = state.get("refund_amount", 0.0)

    tool_result: dict = {}
    response_message = "No automated action was required for this request."

    if planned_action == "order_lookup":
        tool_result = mock_order_lookup(order_id)
        response_message = tool_result["message"]
        audit_action = "order_lookup"
    elif planned_action == "policy_check":
        tool_result = mock_policy_check(order_id, refund_amount)
        response_message = tool_result["message"]
        audit_action = "policy_check"
    elif planned_action == "refund":
        policy_result = mock_policy_check(order_id, refund_amount)
        if policy_result["eligible"]:
            tool_result = mock_refund_tool(order_id, refund_amount)
            response_message = tool_result["message"]
            audit_action = "refund"
        else:
            tool_result = policy_result
            response_message = policy_result["message"]
            audit_action = "policy_check"
    else:
        audit_action = "none"

    audit_entry = {
        "step": "tool_executor",
        "action": audit_action,
        "planned_action": planned_action,
        "order_id": order_id,
        "refund_amount": refund_amount,
        "tool_result": tool_result,
    }

    return {
        "messages": [AIMessage(content=response_message)],
        "audit_log": _append_audit(state.get("audit_log", []), audit_entry),
    }


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def route_after_planner(state: AgentState) -> str:
    if state.get("requires_human_approval"):
        return "human_gate"
    planner_ctx = _get_planner_context(state)
    if planner_ctx.get(PLANNED_ACTION_KEY) in ("order_lookup", "policy_check", "refund"):
        return "tool_executor"
    return END


def route_after_human_gate(state: AgentState) -> str:
    if state.get("requires_human_approval"):
        return END
    planner_ctx = _get_planner_context(state)
    if planner_ctx.get(PLANNED_ACTION_KEY) in ("order_lookup", "policy_check", "refund"):
        return "tool_executor"
    return END


# ---------------------------------------------------------------------------
# Graph compilation
# ---------------------------------------------------------------------------


def build_graph():
    """Compile the support agent graph with an in-memory checkpointer."""
    workflow = StateGraph(AgentState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("human_gate", human_gate_node)
    workflow.add_node("tool_executor", tool_executor_node)

    workflow.set_entry_point("planner")

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
    """
    Convenience wrapper to run the graph for a single user turn.

    Returns the final state dict including messages and audit_log.
    """
    config = {"configurable": {"thread_id": thread_id}}
    initial_state: AgentState = {
        "messages": [HumanMessage(content=user_message)],
        "order_id": order_id,
        "refund_amount": refund_amount,
        "requires_human_approval": False,
        "audit_log": [],
    }
    return graph.invoke(initial_state, config=config)


def resume_agent(human_decision: dict | bool, *, thread_id: str = "default") -> dict:
    """Resume a paused graph after human gate interrupt."""
    config = {"configurable": {"thread_id": thread_id}}
    return graph.invoke(Command(resume=human_decision), config=config)
