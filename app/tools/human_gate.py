"""
Human-in-the-loop gate simulation.

When the agent cannot resolve autonomously (high-value refund, policy
exception, angry escalation), this tool pauses the graph and records a
handoff request for a human agent.

In production this would integrate with a ticketing / queue system; here
it writes to the audit log and returns a simulated ticket ID.
"""

from __future__ import annotations

import uuid
from typing import Any

from langchain_core.tools import tool

from app.governance.audit import log_event


@tool
def escalate_to_human(reason: str, order_id: str | None = None) -> dict[str, Any]:
    """
    Escalate the current interaction to a human support agent.
    
    Args:
        reason: The reason for the escalation (e.g. legal threat, customer request).
        order_id: The order ID associated with the escalation, if any.
    """
    ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
    details = {
        "ticket_id": ticket_id,
        "reason": reason,
        "order_id": order_id or "none",
        "status": "queued",
    }
    
    log_event("human_escalation", details, risk_level="high")
    
    return {
        "status": "escalated",
        "ticket_id": ticket_id,
        "message": (
            f"This request has been escalated to our human support team. "
            f"Ticket reference: {ticket_id}. Reason: {reason}."
        ),
    }
