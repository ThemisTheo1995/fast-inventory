from erp.api.modules.inventory.enums import StockMovementType


def test_order_type_enum_values():
    """Verifies the StockMovementType enum string values."""
    assert StockMovementType.SELL_ORDER == "SELL_ORDER"
    assert StockMovementType.PURCHASE_ORDER == "PURCHASE_ORDER"
    assert StockMovementType.MANUAL_ADJUSTMENT == "MANUAL_ADJUSTMENT"
    assert StockMovementType.BIN_TRANSFER == "BIN_TRANSFER"
    assert StockMovementType.BIN_MERGE == "BIN_MERGE"
