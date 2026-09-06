import re
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from erp.api.modules.customer.exceptions import (
    CustomerNameMustNotContainNumbersError,
)


def validate_and_format_name(value: str | None) -> str | None:
    if value is None:
        return None

    value = value.strip()

    if any(char.isdigit() for char in value):
        raise CustomerNameMustNotContainNumbersError()

    return re.sub(
        r"(^|[\s-])\S",
        lambda match: match.group(0).upper(),
        value.lower(),
    )


def sanitize_email(value: str) -> str:
    return value.strip().lower()


FirstName = Annotated[
    str,
    Field(min_length=2, max_length=50),
    BeforeValidator(validate_and_format_name),
]

LastName = Annotated[
    str | None,
    Field(max_length=50),
    BeforeValidator(validate_and_format_name),
]

Email = Annotated[
    str,
    Field(min_length=3, max_length=255),
    BeforeValidator(sanitize_email),
]


class CustomerBase(BaseModel):
    first_name: FirstName
    last_name: LastName
    email: Email


class CustomerCreate(CustomerBase):
    """Payload for creating a new customer."""


class CustomerUpdate(BaseModel):
    """Payload for partially updating a customer."""

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
