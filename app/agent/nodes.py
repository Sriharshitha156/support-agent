"""
LangGraph node functions for the Customer Support Resolution Agent.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.agent.state import AgentState
from app.governance.audit import log_event
from app.governance.refusal import verify_compliance
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

PlannedAction = Literal["none", "order_lookup", "policy_check", "refund", "refuse_out_of_scope"]
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
OUT_OF_SCOPE_KEYWORDS = ("competitor", "who is better", "better than", "compare you to")

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
    if _is_out_of_scope(text):
        return "out_of_scope"
    if any(keyword in lowered for keyword in ORDER_STATUS_KEYWORDS) or "status" in lowered:
        return "order_status"
    if "where is" in lowered and _extract_order_id(text):
        return "order_status"
    if any(keyword in lowered for keyword in REFUND_REQUEST_KEYWORDS):
        return "refund"
    return "general"


def _is_out_of_scope(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in OUT_OF_SCOPE_KEYWORDS)


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
# LLM Orchestration & Fallback Helper
# ---------------------------------------------------------------------------


class RiskScan(BaseModel):
    legal_threat: bool = Field(description="True if customer mentions legal action, sue, lawyers, or formal legal complaints.")
    detected_keywords: list[str] = Field(description="Specific risk or legal keywords found in the text.")
    refund_requested: bool = Field(description="True if the customer is requesting a refund, return, or compensation.")


class AnalysisPlan(BaseModel):
    intent: str = Field(description="One of: 'order_status', 'refund', 'general', or 'out_of_scope'.")
    order_id: str = Field(description="Extracted order ID (e.g. ORD-1001 or A4821) or empty string.")
    refund_amount: float = Field(description="Extracted refund amount (in USD) or 0.0.")


def _get_llm() -> ChatOpenAI | None:
    g_token = os.getenv("GITHUB_TOKEN")
    o_key = os.getenv("OPENAI_API_KEY")
    
    openai_key = None
    if g_token and not g_token.startswith("gh-your-github-token"):
        openai_key = g_token
    elif o_key and not o_key.startswith("sk-your-openai-api-key"):
        openai_key = o_key
        
    base_url = os.getenv("OPENAI_API_BASE")
    
    # Auto-detect GitHub Models endpoint if a GitHub PAT is used
    if openai_key and (openai_key.startswith("ghp_") or openai_key.startswith("github_pat_") or g_token):
        if not base_url:
            base_url = "https://models.inference.ai.azure.com"
            
    if openai_key and openai_key.lower() != "offline":
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        try:
            # We set max_retries=0 to fail fast if the key is invalid
            llm = ChatOpenAI(
                openai_api_key=openai_key, 
                model=model_name, 
                temperature=0.0, 
                max_retries=0,
                base_url=base_url
            )
            # Quick check
            llm.invoke("probe")
            return llm
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Nodes Implementation
# ---------------------------------------------------------------------------


def preprocess_node(state: AgentState) -> dict:
    """
    Pre-process user input: scan risk keywords and enforce human gate rules.

    For refund requests, escalates when amount > $10 or legal keywords are present.
    """
    user_text = _latest_user_text(state)
    llm = _get_llm()
    
    if llm:
        try:
            structured_llm = llm.with_structured_output(RiskScan)
            scan = structured_llm.invoke(f"Analyze the following support message: {user_text}")
            detected_keywords = scan.detected_keywords
            refund_requested = scan.refund_requested
            legal_threat = scan.legal_threat
        except Exception:
            detected_keywords = _scan_risk_keywords(user_text)
            refund_requested = _is_refund_requested(user_text)
            legal_threat = _has_legal_keywords(user_text)
    else:
        detected_keywords = _scan_risk_keywords(user_text)
        refund_requested = _is_refund_requested(user_text)
        legal_threat = _has_legal_keywords(user_text)

    order_id = state.get("order_id") or _extract_order_id(user_text)
    refund_amount = state.get("refund_amount") or _extract_refund_amount(user_text)

    requires_human_approval = bool(state.get("requires_human_approval", False))
    gate_response: dict = dict(state.get("gate_response", {}))
    audit_log = list(state.get("audit_log", []))

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
    llm = _get_llm()
    
    if llm:
        try:
            structured_llm = llm.with_structured_output(AnalysisPlan)
            plan = structured_llm.invoke(f"Determine the intent and parameters of the following message: {user_text}")
            intent = plan.intent
            order_id = state.get("order_id") or plan.order_id or _extract_order_id(user_text)
            refund_amount = state.get("refund_amount") or plan.refund_amount or _extract_refund_amount(user_text)
        except Exception:
            intent = _detect_intent(user_text)
            order_id = state.get("order_id") or _extract_order_id(user_text)
            refund_amount = state.get("refund_amount") or _extract_refund_amount(user_text)
    else:
        intent = _detect_intent(user_text)
        order_id = state.get("order_id") or _extract_order_id(user_text)
        refund_amount = state.get("refund_amount") or _extract_refund_amount(user_text)

    planned_action: PlannedAction = "none"
    requires_human_approval = bool(state.get("requires_human_approval", False))
    gate_response = dict(state.get("gate_response", {}))
    approval_reason = gate_response.get("reason", "")
    policy_snippets: list[dict] = []

    if intent == "out_of_scope":
        planned_action = "refuse_out_of_scope"
    elif intent == "order_status":
        planned_action = "order_lookup"
        policy_snippets = retrieve_policy(user_text or f"order status {order_id}")
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
    from langgraph.types import interrupt
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
            policy_text = retrieve_policy_text(user_text or f"order status {order_id}")
            tool_result = check_order_status(order_id)
            response_message = f"{tool_result['message']}\n\nRelevant policy:\n{policy_text}"
            audit_action = "order_lookup"
            log_event(
                "policy_retrieval",
                {"step": "tool_executor", "order_id": order_id, "context": "order_status"},
                "low",
            )

        elif planned_action == "refuse_out_of_scope":
            response_message = (
                "I can only assist with order status, refunds, and company support policies. "
                "I cannot compare our service to competitors or answer off-topic requests."
            )
            tool_result = {"status": "refused", "reason": "out_of_scope"}
            audit_action = "refuse_out_of_scope"

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

    compliance = verify_compliance(response_message, state)
    if not compliance["compliant"]:
        # Log policy violation before updating message
        log_event(
            "policy_violation",
            {
                "original_response": response_message,
                "modified_response": compliance["modified_text"],
                "action": compliance["action"],
                "reason": compliance["reason"],
            },
            risk_level="high",
        )
        response_message = compliance["modified_text"]

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
