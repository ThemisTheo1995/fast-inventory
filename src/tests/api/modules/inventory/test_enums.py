from erp.api.modules.inventory.enums import OrderType


def test_order_type_enum_values():
    """Verifies the OrderType enum string values."""
    assert OrderType.SELL_ORDER == "SELL_ORDER"
    assert OrderType.PURCHASE_ORDER == "PURCHASE_ORDER"
    assert OrderType.MANUAL_ADJUSTMENT == "MANUAL_ADJUSTMENT"
