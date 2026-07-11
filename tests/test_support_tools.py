"""Tests for support tools."""

import pytest

from app.tools.support_tools import apply_refund, check_order_status, send_goodwill_credit
from data.mock_orders import OrderNotFoundError


def test_check_order_status():
    result = check_order_status("C1234")
    assert result["order_id"] == "C1234"
    assert "shipped" in result["message"].lower()


def test_apply_refund_within_limit():
    result = apply_refund("C1234", 5.0)
    assert result["status"] == "approved"
    assert "RFND-C1234" in result["confirmation_id"]


def test_apply_refund_over_limit_raises():
    with pytest.raises(ValueError, match="exceeds auto-approval limit"):
        apply_refund("C1234", 25.0)


def test_check_order_status_not_found():
    with pytest.raises(OrderNotFoundError):
        check_order_status("MISSING")


def test_send_goodwill_credit():
    result = send_goodwill_credit(10.0)
    assert result["status"] == "issued"
    assert result["amount"] == 10.0
