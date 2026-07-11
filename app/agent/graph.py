"""
LangGraph graph definition and compilation.

Exports a compiled `graph` with checkpointer for session persistence.

Flow: Request -> Preprocess -> Planner -> [Human Gate | Tool Executor]
      Human Gate -> Wait -> Approve/Reject -> [Tool Executor | End]
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
# Constants
# ---------------------------------------------------------------------------

PlannedAction = Literal["none", "order_lookup", "policy_check", "refund"]
RISK_SCAN_KEYWORDS = ("sue", "lawyer", "legal", "refund", "compensation")
LEGAL_KEYWORDS = ("sue", "lawyer", "legal")
REFUND_REQUEST_KEYWORDS = ("refund", "return", "compensation")
ORDER_STATUS_KEYWORDS = (
    "order status",
    "track my order",
    "where is my order",
    "shipping status",
    "track order",
)
REFUND_THRESHOLD_USD = MAX_AUTO_REFUND_USD
WAITING_APPROVAL_REASON = "High value refund or legal threat detected."
REJECTION_MESSAGE = (
    "Thank you for your patience. After review, we are unable to proceed with "
    "this request automatically. A support specialist will follow up if needed."
)

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
    if any(keyword in lowered for keyword in REFUND_REQUEST_KEYWORDS):
        return "refund"
    return "general"


def _scan_risk_keywords(text: str) -> list[str]:
    lowered = text.lower()
    return [keyword for keyword in RISK_SCAN_KEYWORDS if keyword in lowered]


def _has_legal_keywords(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in LEGAL_KEYWORDS)


def _is_refund_requested(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in REFUND_REQUEST_KEYWORDS)


def _get_planner_context(state: AgentState) -> dict:
    for entry in reversed(state["audit_log"]):
        if entry.get("step") == "planner":
            return entry
    return {}


def _waiting_approval_payload() -> dict:
    return {
        "type": "WAITING_APPROVAL",
        "reason": WAITING_APPROVAL_REASON,
    }


def _normalize_approval_decision(raw_decision: object) -> str:
    if isinstance(raw_decision, str):
        normalized = raw_decision.strip().lower()
        if normalized in ("approve", "reject"):
            return normalized
    if isinstance(raw_decision, dict):
        if raw_decision.get("decision") in ("approve", "reject"):
            return str(raw_decision["decision"])
        if raw_decision.get("approved") is True:
            return "approve"
        if raw_decision.get("approved") is False:
            return "reject"
    if raw_decision is True:
        return "approve"
    if raw_decision is False:
        return "reject"
    return "reject"


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def preprocess_node(state: AgentState) -> dict:
    """
    Pre-process user input: scan risk keywords and enforce human gate rules.

    For refund requests, escalates when amount > $10 or legal keywords are present.
    """
    user_text = _latest_user_text(state)
    detected_keywords = _scan_risk_keywords(user_text)
    order_id = state.get("order_id") or _extract_order_id(user_text)
    refund_amount = state.get("refund_amount") or _extract_refund_amount(user_text)

    requires_human_approval = bool(state.get("requires_human_approval", False))
    gate_response: dict = dict(state.get("gate_response", {}))
    audit_log = list(state.get("audit_log", []))

    refund_requested = _is_refund_requested(user_text)
    legal_threat = _has_legal_keywords(user_text)

    if refund_requested and (refund_amount > REFUND_THRESHOLD_USD or legal_threat):
        requires_human_approval = True
        gate_response = _waiting_approval_payload()
        audit_log = _log_step(
            audit_log,
            event_type="RISK_DETECTED",
            step="preprocess",
            action="RISK_DETECTED: Escalating to human.",
            risk_level="high",
            message="RISK_DETECTED: Escalating to human.",
            detected_keywords=detected_keywords,
            refund_amount=refund_amount,
            legal_threat=legal_threat,
            gate_response=gate_response,
        )

    audit_log = _log_step(
        audit_log,
        event_type="preprocess",
        step="preprocess",
        action="keyword_scan",
        risk_level="high" if requires_human_approval else "low",
        detected_keywords=detected_keywords,
        refund_requested=refund_requested,
        refund_amount=refund_amount,
        legal_threat=legal_threat,
        requires_human_approval=requires_human_approval,
    )

    return {
        "order_id": order_id,
        "refund_amount": refund_amount,
        "requires_human_approval": requires_human_approval,
        "detected_risk_keywords": detected_keywords,
        "gate_response": gate_response,
        "audit_log": audit_log,
    }


def planner_node(state: AgentState) -> dict:
    """Plan the next action based on intent and preprocess risk flags."""
    user_text = _latest_user_text(state)
    intent = _detect_intent(user_text)
    order_id = state.get("order_id") or _extract_order_id(user_text)
    refund_amount = state.get("refund_amount") or _extract_refund_amount(user_text)

    planned_action: PlannedAction = "none"
    requires_human_approval = bool(state.get("requires_human_approval", False))
    gate_response = dict(state.get("gate_response", {}))
    approval_reason = gate_response.get("reason", "")
    policy_snippets: list[dict] = []

    if intent == "order_status":
        planned_action = "order_lookup"
    elif intent == "refund":
        planned_action = "policy_check" if not requires_human_approval else "refund"
        policy_snippets = retrieve_policy(user_text)
        if requires_human_approval and not gate_response:
            gate_response = _waiting_approval_payload()
            approval_reason = gate_response["reason"]

    audit_log = _log_step(
        state.get("audit_log", []),
        event_type="intent_detection",
        step="planner",
        action="intent_detection",
        risk_level="high" if requires_human_approval else "low",
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
        "gate_response": gate_response,
        "audit_log": audit_log,
    }


def human_gate_node(state: AgentState) -> dict:
    """Pause workflow and wait for explicit human approve/reject decision."""
    gate_response = state.get("gate_response") or _waiting_approval_payload()
    pause_message = (
        f"ACTION_REQUIRED: {gate_response['reason']} "
        f"Response type: {gate_response['type']}. Waiting for input."
    )

    audit_log = _log_step(
        state.get("audit_log", []),
        event_type="human_gate_pause",
        step="human_gate",
        action="pause",
        risk_level="high",
        gate_response=gate_response,
        message=pause_message,
    )

    raw_decision = interrupt(gate_response)
    return approve_human_action(
        {**state, "audit_log": audit_log},
        _normalize_approval_decision(raw_decision),
    )


def approve_human_action(state: AgentState, approval_decision: str) -> dict:
    """
    Apply a human decision after the gate pauses.

    - ``approve``: clears the approval flag so the tool executor can run.
    - ``reject``: ends with a polite refusal message.
    """
    decision = approval_decision.strip().lower()
    if decision not in ("approve", "reject"):
        raise ValueError("approval_decision must be 'approve' or 'reject'")

    gate_response = state.get("gate_response") or _waiting_approval_payload()

    if decision == "approve":
        audit_log = _log_step(
            state.get("audit_log", []),
            event_type="human_gate_resume",
            step="human_gate",
            action="approved",
            risk_level="medium",
            gate_response=gate_response,
            approval_decision=decision,
        )
        return {
            "messages": [AIMessage(content="Human approval granted. Proceeding with requested action.")],
            "requires_human_approval": False,
            "approval_status": "approved",
            "gate_response": gate_response,
            "audit_log": audit_log,
        }

    audit_log = _log_step(
        state.get("audit_log", []),
        event_type="human_gate_resume",
        step="human_gate",
        action="rejected",
        risk_level="high",
        gate_response=gate_response,
        approval_decision=decision,
    )
    return {
        "messages": [AIMessage(content=REJECTION_MESSAGE)],
        "requires_human_approval": False,
        "approval_status": "rejected",
        "gate_response": gate_response,
        "audit_log": audit_log,
    }


def tool_executor_node(state: AgentState) -> dict:
    """Execute support tools only when human approval is not required."""
    if state.get("requires_human_approval"):
        audit_log = _log_step(
            state.get("audit_log", []),
            event_type="tool_skipped",
            step="tool_executor",
            action="skipped",
            risk_level="medium",
            reason="requires_human_approval is True — apply_refund blocked",
        )
        return {
            "messages": [AIMessage(content="Tool execution blocked: awaiting human approval.")],
            "audit_log": audit_log,
        }

    if state.get("approval_status") == "rejected":
        audit_log = _log_step(
            state.get("audit_log", []),
            event_type="tool_skipped",
            step="tool_executor",
            action="skipped",
            risk_level="low",
            reason="human rejection — tools not executed",
        )
        return {"messages": [AIMessage(content=REJECTION_MESSAGE)], "audit_log": audit_log}

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
                if state.get("requires_human_approval"):
                    raise ValueError("apply_refund blocked: human approval required")
                tool_result = apply_refund(order_id, refund_amount)
                response_message = tool_result["message"]
                audit_action = "refund"
                risk_level = "medium"
            else:
                order_info = check_order_status(order_id)
                if (
                    order_info.get("days_late", 0) >= 3
                    and order_info.get("total_usd", 0) <= REFUND_THRESHOLD_USD
                ):
                    credit_amount = min(10.0, order_info["total_usd"])
                    tool_result = send_goodwill_credit(credit_amount)
                    response_message = f"{tool_result['message']} Policy applied:\n{policy_text}"
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
                {"step": "tool_executor", "order_id": order_id, "policy_snippets": policy_snippets},
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
    if state.get("approval_status") == "rejected":
        return END
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
