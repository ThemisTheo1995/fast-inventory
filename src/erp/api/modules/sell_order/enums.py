from enum import StrEnum


class SOStatusEnum(StrEnum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    FULLFILLED = "FULLFILLED"
    RETURNED = "RETURNED"
    CANCELLED = "CANCELLED"
    CLOSED = "CLOSED"

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").title()
