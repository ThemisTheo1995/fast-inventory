import re
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from src.erp.api.modules.supplier.exceptions import SupplierNameMustNotContainNumbersError


def validate_and_format_supplier_name(v: str | None) -> str | None:
    if v is None:
        return None

    if any(char.isdigit() for char in v):
        raise SupplierNameMustNotContainNumbersError()

    return re.sub(r"(^|[\s-])\S", lambda m: m.group(0).upper(), v.strip().lower())


def sanitize_supplier_email_logic(v: str | None) -> str | None:
    if v is None:
        return None
    return v.lower().strip()


SupplierName = Annotated[str, Field(min_length=2, max_length=255), BeforeValidator(validate_and_format_supplier_name)]
SupplierEmail = Annotated[str | None, BeforeValidator(sanitize_supplier_email_logic), Field(default=None)]


class SupplierBase(BaseModel):
    name: SupplierName
    email: SupplierEmail


class SupplierCreate(SupplierBase):
    """Payload for creating a new supplier."""

    pass


class SupplierUpdate(SupplierBase):
    """Payload for patching a supplier."""

    pass


class SupplierResponse(SupplierBase):
    """Payload returned to the client."""

    id: UUID
    workspace_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupplierPaginatedResponse(BaseModel):
    """Payload for paginated supplier lists."""

    items: list[SupplierResponse]
    total: int
