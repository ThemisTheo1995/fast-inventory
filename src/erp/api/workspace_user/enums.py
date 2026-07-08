from enum import StrEnum


class WorkspaceRoleEnum(StrEnum):
    FULL_ADMIN = "full_admin"
    EDIT_ONLY = "edit_only"
    READ_ONLY = "read_only"

    @property
    def label(self) -> str:
        labels = {"full_admin": "Full Admin", "edit_only": "Edit Only", "read_only": "Read Only"}
        return labels[self.value]


class InvitationStatusEnum(StrEnum):
    ACTIVE = "active"
    PENDING = "pending"

    @property
    def label(self) -> str:
        labels = {"active": "Active", "pending": "Pending"}
        return labels[self.value]
