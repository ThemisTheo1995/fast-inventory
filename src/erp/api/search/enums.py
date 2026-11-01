from enum import StrEnum


class EntityTypeEnum(StrEnum):
    BIN = "bin"
    CUSTOMER = "customer"
    SUPPLIER = "supplier"
    ITEM = "item"
    SELL_ORDER = "sell_order"
    PURCHASE_ORDER = "purchase_order"
    INVENTORY = "inventory"
    STOCK_MOVEMENT = "stock_movement"

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").title()
