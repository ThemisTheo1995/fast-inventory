import re
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from src.erp.api.modules.customer.exceptions import CustomerNameMustNotContainNumbersError


def validate_and_format_name(v: str | None) -> str | None:
    if v is None:
        return None

    if any(char.isdigit() for char in v):
        raise CustomerNameMustNotContainNumbersError()

    return re.sub(r"(^|[\s-])\S", lambda m: m.group(0).upper(), v.strip().lower())


def sanitize_email_logic(v: str) -> str:
    return v.lower().strip()


FirstName = Annotated[str, Field(min_length=2, max_length=50), BeforeValidator(validate_and_format_name)]
LastName = Annotated[str, Field(max_length=50), BeforeValidator(validate_and_format_name)]
Email = Annotated[str, BeforeValidator(sanitize_email_logic)]


class CustomerBase(BaseModel):
    first_name: FirstName
    last_name: LastName
    email: Email


class CustomerCreate(CustomerBase):
    """Payload for creating a new customer. All fields are mandatory."""

    pass


class CustomerUpdate(BaseModel):
    """Payload for patching a customer. All fields are optional."""

    first_name: FirstName | None = None
    last_name: LastName | None = None
    email: Email | None = None


class CustomerResponse(CustomerBase):
    """Payload returned to the client."""

    id: UUID
    workspace_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerPaginatedResponse(BaseModel):
    """Payload for paginated customer lists."""

    items: list[CustomerResponse]
    total: int
