from enum import StrEnum


class EbayPermissionRole(StrEnum):
    FULL_ADMIN = "FULL_ADMIN"
    EDITOR = "EDITOR"
    READER = "READER"
