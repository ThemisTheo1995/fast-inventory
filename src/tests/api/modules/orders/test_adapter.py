from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.erp.api.modules.orders.adapter import MarketplaceOrderAdapter
from src.erp.api.modules.orders.schemas import MarketplaceCreateOrder, MarketplaceOrder

# ============================================================================
# CONFORMING TEST IMPLEMENTATION
# ============================================================================


class DummyConformingAdapter:
    """A minimal mock class that fully implements the order protocol contract."""

    def get_orders(self, since: datetime) -> list[MarketplaceOrder]:  # noqa: ARG002
        return []

    def create_order(self, order: MarketplaceCreateOrder) -> MarketplaceOrder:  # noqa: ARG002
        # Returns a mock object matching the expected MarketplaceOrder schema
        return MagicMock(spec=MarketplaceOrder)

    def cancel_order(self, order_id: str) -> None:
        pass

    def sync_orders(self) -> list[MarketplaceOrder]:
        return []


class DummyNonConformingAdapter:
    """A broken mock class missing mandatory protocol interface methods."""

    def cancel_order(self, order_id: str) -> None:
        pass


# ============================================================================
# PROTOCOL STRUCTURAL VERIFICATION TESTS
# ============================================================================


def test_conforming_adapter_matches_protocol_signatures():
    """
    Any class implementing the protocol must expose all required methods.
    We verify their presence and basic execution behavior here.
    """
    adapter: MarketplaceOrderAdapter = DummyConformingAdapter()
    now = datetime.now(tz=UTC)

    assert not adapter.get_orders(since=now)
    assert isinstance(adapter.create_order(MagicMock()), MarketplaceOrder)
    assert adapter.cancel_order("ORDER-123") is None
    assert not adapter.sync_orders()


def test_protocol_signature_inspection():
    """
    ARCHITECTURAL GUARD:
    Ensures that the MarketplaceOrderAdapter interface itself maintains its
    strict structural method declarations over time.
    """
    required_methods = [
        "get_orders",
        "create_order",
        "cancel_order",
        "sync_orders",
    ]

    for method in required_methods:
        assert hasattr(MarketplaceOrderAdapter, method), (
            f"Protocol is missing the mandatory '{method}' method contract definition."
        )


def test_runtime_checkable_alternative_insight():
    """
    If you add the `@runtime_checkable` decorator from the typing module
    to your Protocol class definition in production, you can cleanly run
    isinstance() assertions directly inside your test loops like this:
    """
    is_runtime_safe = getattr(MarketplaceOrderAdapter, "_is_runtime_protocol", False)

    if is_runtime_safe:
        # This branch runs if you decide to decorate the Protocol in production
        assert isinstance(DummyConformingAdapter(), MarketplaceOrderAdapter)
        assert not isinstance(DummyNonConformingAdapter(), MarketplaceOrderAdapter)
    else:
        # This branch runs because it's a standard static structural protocol
        with pytest.raises(TypeError, match="Instance and class checks can only be used"):
            isinstance(DummyConformingAdapter(), MarketplaceOrderAdapter)
