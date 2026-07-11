"""Tests for mock order data."""

import pytest

from data.mock_orders import OrderNotFoundError, lookup_order


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
