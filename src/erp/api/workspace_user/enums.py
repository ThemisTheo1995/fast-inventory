from enum import StrEnum


class InvitationStatusEnum(StrEnum):
    ACTIVE = "active"
    PENDING = "pending"

    @property
    def label(self) -> str:
        labels = {"active": "Active", "pending": "Pending"}
        return labels[self.value]
