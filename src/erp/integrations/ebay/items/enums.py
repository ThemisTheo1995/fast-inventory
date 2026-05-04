from enum import StrEnum


class EbayItemStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    DRAFT = "DRAFT"
