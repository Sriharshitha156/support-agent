"""Support tools backed by mock order data."""

from __future__ import annotations

from data.mock_orders import OrderNotFoundError, lookup_order

MAX_AUTO_REFUND_USD = 10.0


def check_order_status(order_id: str) -> dict:
    """Look up order status from the mock order database."""
    order = lookup_order(order_id)
    if order["status"] == "delivered" and order.get("days_late", 0) > 0:
        message = (
            f"Order {order_id} was delivered on {order['actual_delivery']} "
            f"({order['days_late']} days late). {order['notes']}"
        )
    elif order["status"] == "shipped":
        message = (
            f"Order {order_id} is shipped and expected by {order['promised_delivery']}. "
            f"{order['notes']}"
        )
    elif order["status"] == "processing":
        message = f"Order {order_id} is processing. {order['notes']}"
    elif order["status"] == "cancelled":
        message = f"Order {order_id} is cancelled. {order['notes']}"
    else:
        message = f"Order {order_id} status: {order['status']}. {order['notes']}"

    return {
        "order_id": order_id,
        "status": order["status"],
        "total_usd": order["total_usd"],
        "scenario": order["scenario"],
        "days_late": order.get("days_late", 0),
        "message": message,
        "order": order,
    }


def apply_refund(order_id: str, amount: float) -> dict:
    """
    Process a refund against an order.

    Safety net: only auto-executes when amount <= $10.
    """
    if amount > MAX_AUTO_REFUND_USD:
        raise ValueError(
            f"Refund amount ${amount:.2f} exceeds auto-approval limit of "
            f"${MAX_AUTO_REFUND_USD:.2f}. Manager approval required."
        )

    order = lookup_order(order_id)
    confirmation_id = f"RFND-{order_id}-{int(amount * 100)}"

    return {
        "order_id": order_id,
        "refund_amount": amount,
        "confirmation_id": confirmation_id,
        "status": "approved",
        "message": (
            f"Refund of ${amount:.2f} approved and initiated for order {order_id}. "
            f"Confirmation: {confirmation_id}."
        ),
        "order": order,
    }


def send_goodwill_credit(amount: float) -> dict:
    """Issue a mock goodwill credit to the customer."""
    credit_id = f"GWC-{int(amount * 100)}"
    return {
        "credit_id": credit_id,
        "amount": amount,
        "status": "issued",
        "message": f"Goodwill credit of ${amount:.2f} issued. Reference: {credit_id}.",
    }


__all__ = [
    "OrderNotFoundError",
    "MAX_AUTO_REFUND_USD",
    "apply_refund",
    "check_order_status",
    "send_goodwill_credit",
]
