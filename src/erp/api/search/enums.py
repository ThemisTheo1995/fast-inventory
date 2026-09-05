from enum import StrEnum


class EntityTypeEnum(StrEnum):
    CUSTOMER = "customer"
    SUPPLIER = "supplier"
    ITEM = "item"
    SELL_ORDER = "sell_order"
    INVENTORY = "inventory"
    STOCK_MOVEMENT = "stock_movementt"

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").title()
