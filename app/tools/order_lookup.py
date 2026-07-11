"""
Mock order lookup tool.

Queries the mock order database in `data/orders/` to retrieve order status,
line items, shipping info, and eligibility flags.

Exposed to the agent as a LangChain StructuredTool with inputs:
- order_id: str
- customer_id: str (for ownership verification)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from langchain_core.tools import tool

ORDERS_JSON_PATH = Path(__file__).resolve().parents[2] / "data" / "orders" / "mock_orders.json"


class OrderVerificationError(ValueError):
    """Raised when an order does not belong to the requesting customer."""


def load_orders_db() -> list[dict[str, Any]]:
    """Load the orders list from mock_orders.json."""
    if not ORDERS_JSON_PATH.exists():
        return []
    try:
        with open(ORDERS_JSON_PATH, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data.get("orders", [])
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Error loading orders database: {exc}")
        return []


@tool
def lookup_order_details(order_id: str, customer_id: str | None = None) -> dict[str, Any]:
    """
    Look up order status, items, and verification details from the JSON database.
    
    Args:
        order_id: The ID of the order to look up (e.g. ORD-1001).
        customer_id: Optional customer ID to verify ownership.
    """
    orders = load_orders_db()
    normalized_order_id = order_id.strip().upper()
    
    target_order = None
    for order in orders:
        if order.get("order_id", "").upper() == normalized_order_id:
            target_order = order
            break
            
    if not target_order:
        # Fallback check against in-memory mock database if not found in JSON
        try:
            from data.mock_orders import lookup_order
            legacy_order = lookup_order(normalized_order_id)
            if legacy_order:
                target_order = {
                    "order_id": legacy_order["order_id"],
                    "customer_id": legacy_order["customer_id"],
                    "status": legacy_order["status"],
                    "total_usd": legacy_order["total_usd"],
                    "items": legacy_order.get("items", []),
                    "refund_eligible": legacy_order.get("refund_eligible", True)
                }
        except Exception:
            raise ValueError(f"Order {order_id} not found.")

    if not target_order:
        raise ValueError(f"Order {order_id} not found.")
        
    if customer_id:
        normalized_cust_id = customer_id.strip().upper()
        order_cust_id = target_order.get("customer_id", "").upper()
        if order_cust_id != normalized_cust_id:
            raise OrderVerificationError(
                f"Verification failed: Order {order_id} does not belong to customer {customer_id}."
            )
            
    return target_order
