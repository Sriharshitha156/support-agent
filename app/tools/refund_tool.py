"""
Mock refund processing tool.

Simulates initiating a refund against an order. Validates:
- order exists and belongs to customer
- order is within refund window per policy (30 days)
- refund amount does not exceed governance limits ($10 limit for auto-approval)

Returns a mock confirmation ID or a structured rejection reason.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from langchain_core.tools import tool

from app.tools.order_lookup import lookup_order_details, OrderVerificationError

REFUND_WINDOW_DAYS = 30
MAX_AUTO_REFUND_LIMIT = 10.0


@tool
def process_order_refund(
    order_id: str, 
    customer_id: str, 
    amount: float,
    reason: str = "Customer request"
) -> dict[str, Any]:
    """
    Process and validate a refund against an order.
    
    Args:
        order_id: The ID of the order to refund (e.g. ORD-1001).
        customer_id: The ID of the requesting customer.
        amount: The refund amount requested in USD.
        reason: The reason for the refund.
    """
    # 1. Look up order and verify ownership
    try:
        order = lookup_order_details.func(order_id, customer_id)
    except OrderVerificationError as exc:
        return {
            "status": "rejected",
            "reason": "ownership_verification_failed",
            "message": str(exc),
        }
    except ValueError as exc:
        return {
            "status": "rejected",
            "reason": "order_not_found",
            "message": str(exc),
        }
        
    # 2. Check policy limit for auto-approval
    if amount > MAX_AUTO_REFUND_LIMIT:
        return {
            "status": "escalated",
            "reason": "requires_manager_approval",
            "message": f"Refund of ${amount:.2f} exceeds automatic approval limit of ${MAX_AUTO_REFUND_LIMIT:.2f}.",
            "order": order,
        }
        
    # 3. Verify refund eligibility flag
    if not order.get("refund_eligible", True):
        return {
            "status": "rejected",
            "reason": "not_eligible_for_refund",
            "message": f"Order {order_id} is marked as ineligible for a refund.",
            "order": order,
        }
        
    # 4. Check refund window (30 days from delivery)
    delivered_at_str = order.get("delivered_at")
    if delivered_at_str:
        try:
            # Replace Z with +00:00 to support older Python fromisoformat implementations if needed
            cleaned_date = delivered_at_str.replace("Z", "+00:00")
            delivered_date = datetime.fromisoformat(cleaned_date)
            now = datetime.now(timezone.utc)
            delta = now - delivered_date
            
            if delta.days > REFUND_WINDOW_DAYS:
                return {
                    "status": "rejected",
                    "reason": "refund_window_expired",
                    "message": f"Refund window of {REFUND_WINDOW_DAYS} days has expired. Delivered {delta.days} days ago.",
                    "order": order,
                }
        except ValueError:
            pass # Ignore malformed dates and proceed with default checks
            
    # 5. Success
    confirmation_id = f"RFND-{order_id}-{int(amount * 100)}"
    return {
        "status": "approved",
        "confirmation_id": confirmation_id,
        "refund_amount": amount,
        "message": f"Refund of ${amount:.2f} approved and initiated. Confirmation: {confirmation_id}.",
        "order": order,
    }
