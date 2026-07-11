"""Tests for mock order data and structured tools."""

from __future__ import annotations

import pytest

from data.mock_orders import OrderNotFoundError, lookup_order
from app.tools.order_lookup import lookup_order_details, OrderVerificationError
from app.tools.refund_tool import process_order_refund
from app.tools.human_gate import escalate_to_human


def test_lookup_known_orders():
    order = lookup_order("A4821")
    assert order["scenario"] == "late_delivery"
    assert order["days_late"] == 5

    high_value = lookup_order("B9999")
    assert high_value["total_usd"] == 500.0

    normal = lookup_order("C1234")
    assert normal["scenario"] == "normal"


def test_lookup_order_not_found():
    with pytest.raises(OrderNotFoundError, match="Not Found"):
        lookup_order("Z0000")


# --- Structured Tools Tests ---

def test_structured_lookup_order_details():
    # Test lookup from JSON database
    order = lookup_order_details.invoke({"order_id": "ORD-1001"})
    assert order["customer_id"] == "CUST-001"
    assert order["total_usd"] == 49.99

    # Test ownership verification success
    order_verified = lookup_order_details.invoke({"order_id": "ORD-1001", "customer_id": "CUST-001"})
    assert order_verified["order_id"] == "ORD-1001"

    # Test ownership verification failure
    with pytest.raises(OrderVerificationError):
        lookup_order_details.invoke({"order_id": "ORD-1001", "customer_id": "CUST-999"})

    # Test fallback to memory mock data
    legacy = lookup_order_details.invoke({"order_id": "A4821"})
    assert legacy["customer_id"] == "CUST-101"

    # Test order not found
    with pytest.raises(ValueError, match="not found"):
        lookup_order_details.invoke({"order_id": "ORD-UNKNOWN"})


def test_structured_process_order_refund():
    # Test valid auto-approved small refund
    # Note: ORD-1001 was delivered on 2026-06-01. If we are running in July 2026, it is > 30 days.
    # Let's bypass date verification in unit tests by mocking or using ORD-1002/legacy orders.
    # Wait, process_order_refund uses lookup_order_details. Let's test a legacy order like C1234 or D5678 that has no delivered_at date (so refund window check passes)
    result = process_order_refund.invoke({
        "order_id": "C1234",
        "customer_id": "CUST-303",
        "amount": 5.0
    })
    assert result["status"] == "approved"
    assert "RFND-C1234" in result["confirmation_id"]
    
    # Test refund exceeding auto-approval limit (escalated)
    result_large = process_order_refund.invoke({
        "order_id": "C1234",
        "customer_id": "CUST-303",
        "amount": 25.0
    })
    assert result_large["status"] == "escalated"
    assert result_large["reason"] == "requires_manager_approval"

    # Test ineligible order refund (ORD-1002 has refund_eligible = False)
    result_ineligible = process_order_refund.invoke({
        "order_id": "ORD-1002",
        "customer_id": "CUST-002",
        "amount": 5.0
    })
    assert result_ineligible["status"] == "rejected"
    assert result_ineligible["reason"] == "not_eligible_for_refund"

    # Test expired refund window (ORD-1001 delivered on 2026-06-01, > 30 days from July 11, 2026)
    result_expired = process_order_refund.invoke({
        "order_id": "ORD-1001",
        "customer_id": "CUST-001",
        "amount": 5.0
    })
    assert result_expired["status"] == "rejected"
    assert result_expired["reason"] == "refund_window_expired"


def test_structured_escalate_to_human():
    res = escalate_to_human.invoke({"reason": "angry customer escalation", "order_id": "ORD-1001"})
    assert res["status"] == "escalated"
    assert "ticket_id" in res
    assert "TKT-" in res["ticket_id"]
