from enum import StrEnum


class OrderType(StrEnum):
    SELL_ORDER = "SELL_ORDER"
    PURCHASE_ORDER = "PURCHASE_ORDER"
    MANUAL_ADJUSTMENT = "MANUAL_ADJUSTMENT"
