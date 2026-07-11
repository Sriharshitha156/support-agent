"""
LangGraph graph definition and compilation.

Exports a compiled `graph` with checkpointer for session persistence.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from app.agent.state import AgentState
from app.governance.audit import log_event
from app.rag.policy_retriever import retrieve_policy, retrieve_policy_text
from app.tools.support_tools import (
    MAX_AUTO_REFUND_USD,
    apply_refund,
    check_order_status,
    send_goodwill_credit,
)
from data.mock_orders import OrderNotFoundError

# ---------------------------------------------------------------------------
# Constants & routing labels
# ---------------------------------------------------------------------------

PlannedAction = Literal["none", "order_lookup", "policy_check", "refund"]
ESCALATION_KEYWORDS = ("sue", "lawyer", "complaint")
REFUND_KEYWORDS = ("refund", "return")
ORDER_STATUS_KEYWORDS = (
    "order status",
    "track my order",
    "where is my order",
    "shipping status",
    "track order",
)
REFUND_THRESHOLD_USD = MAX_AUTO_REFUND_USD

PLANNED_ACTION_KEY = "planned_action"
APPROVAL_REASON_KEY = "approval_reason"


# ---------------------------------------------------------------------------
# Audit helpers
# ---------------------------------------------------------------------------


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_audit(audit_log: list[dict], entry: dict) -> list[dict]:
    return audit_log + [{**entry, "timestamp": _utcnow()}]


def _log_step(
    audit_log: list[dict],
    *,
    event_type: str,
    step: str,
    action: str,
    risk_level: str = "low",
    **details,
) -> list[dict]:
    """Append to in-memory state audit log and persist via governance audit."""
    payload = {"step": step, "action": action, **details}
    log_event(event_type, payload, risk_level)
    return _append_audit(audit_log, payload)


def _latest_user_text(state: AgentState) -> str:
    for message in reversed(state["messages"]):
        if isinstance(message, HumanMessage):
            return message.content if isinstance(message.content, str) else str(message.content)
    return ""


def _extract_order_id(text: str) -> str:
    order_match = re.search(r"\b[A-Z]\d{4}\b", text, re.IGNORECASE)
    if order_match:
        return order_match.group(0).upper()

    legacy_match = re.search(r"ORD-\d+", text, re.IGNORECASE)
    return legacy_match.group(0).upper() if legacy_match else ""


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


def _risk_for_refund(amount: float, escalation: bool) -> str:
    if escalation:
        return "high"
    if amount > REFUND_THRESHOLD_USD:
        return "high"
    if amount > 0:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def planner_node(state: AgentState) -> dict:
    """Analyze user input, retrieve policy context, and plan the next action."""
    user_text = _latest_user_text(state)
    intent = _detect_intent(user_text)
    order_id = state.get("order_id") or _extract_order_id(user_text)
    refund_amount = state.get("refund_amount") or _extract_refund_amount(user_text)

    planned_action: PlannedAction = "none"
    requires_human_approval = False
    approval_reason = ""
    policy_snippets: list[dict] = []

    escalation_hit = next((kw for kw in ESCALATION_KEYWORDS if kw in user_text.lower()), None)

    if intent == "order_status":
        planned_action = "order_lookup"
    elif intent == "refund":
        planned_action = "policy_check"
        policy_snippets = retrieve_policy(user_text)
        if escalation_hit:
            requires_human_approval = True
            approval_reason = f"escalation language detected ('{escalation_hit}')"
            planned_action = "refund"
        elif refund_amount > REFUND_THRESHOLD_USD:
            requires_human_approval = True
            approval_reason = (
                f"refund amount ${refund_amount:.2f} exceeds "
                f"${REFUND_THRESHOLD_USD:.2f} threshold"
            )

    risk_level = _risk_for_refund(refund_amount, bool(escalation_hit))
    audit_log = _log_step(
        state.get("audit_log", []),
        event_type="intent_detection",
        step="planner",
        action="intent_detection",
        risk_level=risk_level,
        intent=intent,
        **{
            PLANNED_ACTION_KEY: planned_action,
            "order_id": order_id,
            "refund_amount": refund_amount,
            "requires_human_approval": requires_human_approval,
            APPROVAL_REASON_KEY: approval_reason,
            "user_text_excerpt": user_text[:200],
            "policy_snippets": policy_snippets,
        },
    )

    return {
        "order_id": order_id,
        "refund_amount": refund_amount,
        "requires_human_approval": requires_human_approval,
        "audit_log": audit_log,
    }


def human_gate_node(state: AgentState) -> dict:
    """Pause for human approval when required."""
    planner_ctx = _get_planner_context(state)
    reason = planner_ctx.get(APPROVAL_REASON_KEY) or "high-risk request"
    pause_message = f"ACTION_REQUIRED: Human approval needed for {reason}. Waiting for input."

    audit_log = _log_step(
        state.get("audit_log", []),
        event_type="human_gate_pause",
        step="human_gate",
        action="pause",
        risk_level="high",
        reason=reason,
        message=pause_message,
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

    audit_log = _log_step(
        audit_log,
        event_type="human_gate_resume",
        step="human_gate",
        action="resume",
        risk_level="high" if not approved else "medium",
        approved=approved,
        human_decision=human_decision,
        message=resolution_message,
    )

    return {
        "messages": [AIMessage(content=resolution_message)],
        "requires_human_approval": not approved,
        "audit_log": audit_log,
    }


def tool_executor_node(state: AgentState) -> dict:
    """Execute support tools when human approval is not required or has been granted."""
    if state.get("requires_human_approval"):
        audit_log = _log_step(
            state.get("audit_log", []),
            event_type="tool_skipped",
            step="tool_executor",
            action="skipped",
            risk_level="medium",
            reason="human approval still required",
        )
        return {
            "messages": [AIMessage(content="Tool execution blocked: awaiting human approval.")],
            "audit_log": audit_log,
        }

    planner_ctx = _get_planner_context(state)
    planned_action: PlannedAction = planner_ctx.get(PLANNED_ACTION_KEY, "none")
    order_id = state.get("order_id", "")
    refund_amount = state.get("refund_amount", 0.0)
    user_text = _latest_user_text(state)

    tool_result: dict = {}
    response_message = "No automated action was required for this request."
    audit_action = "none"
    risk_level = "low"

    try:
        if planned_action == "order_lookup":
            tool_result = check_order_status(order_id)
            response_message = tool_result["message"]
            audit_action = "order_lookup"
            risk_level = "low"

        elif planned_action in ("policy_check", "refund"):
            policy_snippets = retrieve_policy(user_text or f"refund order {order_id}")
            policy_text = retrieve_policy_text(user_text or f"refund order {order_id}")

            if refund_amount > REFUND_THRESHOLD_USD:
                tool_result = {
                    "policy_snippets": policy_snippets,
                    "status": "manager_required",
                    "message": (
                        f"Refund of ${refund_amount:.2f} requires manager approval per policy. "
                        f"Relevant policy:\n{policy_text}"
                    ),
                }
                response_message = tool_result["message"]
                audit_action = "policy_check"
                risk_level = "high"
            elif refund_amount > 0:
                tool_result = apply_refund(order_id, refund_amount)
                response_message = tool_result["message"]
                audit_action = "refund"
                risk_level = "medium"
            else:
                order_info = check_order_status(order_id)
                if order_info.get("days_late", 0) >= 3 and order_info.get("total_usd", 0) <= REFUND_THRESHOLD_USD:
                    credit_amount = min(10.0, order_info["total_usd"])
                    tool_result = send_goodwill_credit(credit_amount)
                    response_message = (
                        f"{tool_result['message']} Policy applied:\n{policy_text}"
                    )
                    audit_action = "goodwill_credit"
                else:
                    tool_result = {
                        "policy_snippets": policy_snippets,
                        "order": order_info,
                        "status": "policy_review",
                    }
                    response_message = (
                        f"Policy review for order {order_id}:\n{policy_text}\n"
                        f"Order status: {order_info['message']}"
                    )
                    audit_action = "policy_check"

            log_event(
                "policy_retrieval",
                {
                    "step": "tool_executor",
                    "order_id": order_id,
                    "policy_snippets": policy_snippets,
                },
                "medium",
            )

    except OrderNotFoundError:
        response_message = f"Order {order_id or 'unknown'} was not found."
        tool_result = {"error": "Not Found", "order_id": order_id}
        audit_action = "order_not_found"
        risk_level = "medium"
    except ValueError as exc:
        response_message = str(exc)
        tool_result = {"error": str(exc), "order_id": order_id, "refund_amount": refund_amount}
        audit_action = "refund_blocked"
        risk_level = "high"

    audit_log = _log_step(
        state.get("audit_log", []),
        event_type="tool_execution",
        step="tool_executor",
        action=audit_action,
        risk_level=risk_level,
        planned_action=planned_action,
        order_id=order_id,
        refund_amount=refund_amount,
        tool_result=tool_result,
        response_message=response_message,
    )

    return {
        "messages": [AIMessage(content=response_message)],
        "audit_log": audit_log,
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


def resume_agent(human_decision: dict | bool, *, thread_id: str = "default") -> dict:
    """Resume a paused graph after human gate interrupt."""
    config = {"configurable": {"thread_id": thread_id}}
    return graph.invoke(Command(resume=human_decision), config=config)
