"""
Refusal and policy compliance logic.

Evaluates agent outputs and tool requests before they reach the customer.
Blocks or modifies responses that:
- violate refund limits or eligibility rules
- disclose PII of other customers (e.g. other order IDs or full card numbers)
- promise actions outside agent authority
- bypass required human approval for high-risk operations

Returns allow / refuse / escalate decisions consumed by graph nodes.
"""

from __future__ import annotations

import re
from typing import Any, Dict


class PolicyViolationError(ValueError):
    """Raised when an agent action or response violates support guidelines."""


def check_pii_exposure(text: str, allowed_order_id: str | None = None) -> bool:
    """
    Scan response for potential PII exposure.
    - Full credit card numbers (13-16 digits)
    - Order IDs not matching the current session's order
    """
    # 1. Look for full credit card numbers (e.g. 13 to 16 consecutive digits or hyphenated groups)
    if re.search(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b|\b\d{13,16}\b", text):
        return True
        
    # 2. Look for order IDs matching the ORD-XXXX or AXXXX pattern that aren't the allowed one
    all_order_ids = re.findall(r"\bORD-\d+\b|\b[A-Z]\d{4}\b", text, re.IGNORECASE)
    for oid in all_order_ids:
        oid_upper = oid.upper()
        if allowed_order_id and oid_upper != allowed_order_id.upper():
            return True # Exposure of another order's details
            
    return False


def verify_compliance(response_text: str, state: dict[str, Any]) -> dict[str, Any]:
    """
    Audit response text against compliance and safety guidelines.
    
    Returns a dict with:
    - compliant: bool
    - action: 'allow' | 'refuse' | 'escalate'
    - reason: str (if refused or escalated)
    - modified_text: str (if cleanable)
    """
    allowed_order_id = state.get("order_id")
    refund_amount = state.get("refund_amount", 0.0)
    requires_approval = state.get("requires_human_approval", False)
    approval_status = state.get("approval_status", "")
    
    # 1. PII Exposure Audit
    if check_pii_exposure(response_text, allowed_order_id):
        return {
            "compliant": False,
            "action": "refuse",
            "reason": "PII leakage detected: response contains unauthorized order numbers or card details.",
            "modified_text": "I apologize, but I cannot share sensitive information or details of other orders."
        }
        
    # 2. Unauthorized Promises / Escaped approval audit
    response_lower = response_text.lower()
    promising_refund = any(phrase in response_lower for phrase in ["refund approved", "refund processed", "i have refunded"])
    
    if promising_refund:
        # If agent is promising a refund but it was either escalated or rejected
        if requires_approval and approval_status != "approved":
            return {
                "compliant": False,
                "action": "escalate",
                "reason": "Agent attempted to promise refund before human approval was finalized.",
                "modified_text": "Your refund request is currently awaiting manager review. We will notify you once approved."
            }
        # If refund is > $10 limit and was not approved
        if refund_amount > 10.0 and approval_status != "approved":
            return {
                "compliant": False,
                "action": "escalate",
                "reason": "Agent attempted to promise high-value refund without authorization.",
                "modified_text": "I have routed your refund request of ${:.2f} to a manager for approval.".format(refund_amount)
            }
            
    return {
        "compliant": True,
        "action": "allow",
        "reason": "",
        "modified_text": response_text
    }
