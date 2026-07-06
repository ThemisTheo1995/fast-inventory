from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CustomerBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    email: EmailStr


class CustomerCreate(CustomerBase):
    """Payload for creating a new customer."""

    pass


class CustomerUpdate(BaseModel):
    """Payload for patching a customer"""

    first_name: str | None = Field(default=None, min_length=1, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None


class CustomerResponse(CustomerBase):
    """Payload returned to the client."""

    id: UUID
    workspace_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
