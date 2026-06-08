import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class WorkspaceCreate(BaseModel):
    name: str
    email: EmailStr


class WorkspaceUpdate(BaseModel):
    # Basic Info
    name: str | None = Field(None, max_length=255, description="The name of the workspace")
    email: EmailStr | None = Field(None, description="Workspace contact email")
    phone_number: str | None = Field(None, max_length=20, description="Workspace contact phone number")

    # Location
    country: str | None = Field(None, max_length=100)
    city: str | None = Field(None, max_length=100)
    address_line1: str | None = Field(None, max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    postal_code: str | None = Field(None, max_length=20)

    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        """
        Mirrors the database E.164 validation at the API router level.
        """
        if v is not None and not re.match(r"^\+?[1-9]\d{1,14}$", v):
            # E.164 standard format validation
            msg = "Invalid phone number format. Must be in E.164 format."
            raise ValueError(msg)

        return v


class WorkspaceResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr | None = None
    phone_number: str | None = None

    # Location
    country: str | None = None
    city: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    postal_code: str | None = None

    model_config = ConfigDict(from_attributes=True)
