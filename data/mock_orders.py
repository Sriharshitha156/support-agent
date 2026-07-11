"""Mock order database for the Customer Support Resolution Agent."""

from __future__ import annotations

MOCK_ORDERS: dict[str, dict] = {
    "A4821": {
        "order_id": "A4821",
        "customer_id": "CUST-101",
        "status": "delivered",
        "total_usd": 89.99,
        "items": [{"sku": "HEADPHONES-PRO", "qty": 1, "price_usd": 89.99}],
        "promised_delivery": "2026-07-01",
        "actual_delivery": "2026-07-06",
        "days_late": 5,
        "scenario": "late_delivery",
        "refund_eligible": True,
        "notes": "Delivered 5 days late.",
    },
    "B9999": {
        "order_id": "B9999",
        "customer_id": "CUST-202",
        "status": "delivered",
        "total_usd": 500.00,
        "items": [{"sku": "SMARTWATCH-ELITE", "qty": 1, "price_usd": 500.00}],
        "promised_delivery": "2026-06-28",
        "actual_delivery": "2026-06-30",
        "days_late": 0,
        "scenario": "high_value",
        "refund_eligible": False,
        "notes": "High-value order; manager approval required for refunds.",
    },
    "C1234": {
        "order_id": "C1234",
        "customer_id": "CUST-303",
        "status": "shipped",
        "total_usd": 34.50,
        "items": [{"sku": "USB-CABLE", "qty": 2, "price_usd": 17.25}],
        "promised_delivery": "2026-07-12",
        "actual_delivery": None,
        "days_late": 0,
        "scenario": "normal",
        "refund_eligible": True,
        "notes": "In transit; on schedule.",
    },
    "D5678": {
        "order_id": "D5678",
        "customer_id": "CUST-404",
        "status": "processing",
        "total_usd": 120.00,
        "items": [{"sku": "KEYBOARD-MECH", "qty": 1, "price_usd": 120.00}],
        "promised_delivery": "2026-07-15",
        "actual_delivery": None,
        "days_late": 0,
        "scenario": "processing",
        "refund_eligible": True,
        "notes": "Order is being prepared for shipment.",
    },
    "E9012": {
        "order_id": "E9012",
        "customer_id": "CUST-505",
        "status": "cancelled",
        "total_usd": 45.00,
        "items": [{"sku": "PHONE-CASE", "qty": 1, "price_usd": 45.00}],
        "promised_delivery": None,
        "actual_delivery": None,
        "days_late": 0,
        "scenario": "cancelled",
        "refund_eligible": False,
        "notes": "Cancelled by customer before shipment.",
    },
}


class OrderNotFoundError(LookupError):
    """Raised when an order ID does not exist in the mock database."""


def lookup_order(order_id: str) -> dict:
    """Return order data for the given ID or raise Not Found."""
    normalized = order_id.strip().upper()
    if normalized not in MOCK_ORDERS:
        raise OrderNotFoundError("Not Found")
    return dict(MOCK_ORDERS[normalized])
