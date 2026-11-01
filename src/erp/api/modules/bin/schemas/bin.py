from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BinBase(BaseModel):
    code: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern=r"^[A-Za-z0-9\-_.\s]+$",
        description="Unique code identifying the bin (e.g., 'A-01-03')",
    )
    zone: str | None = Field(
        default=None,
        max_length=50,
        description="Warehouse zone or section (e.g., 'Warehouse A')",
    )

    @field_validator("code")
    @classmethod
    def validate_and_normalize_code(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            msg = "Bin code cannot be empty."
            raise ValueError(msg)
        return v

    @field_validator("zone")
    @classmethod
    def validate_and_normalize_zone(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            return v if v else None
        return v


class BinCreate(BinBase):
    """Payload for creating a new bin."""


class BinUpdate(BaseModel):
    """Payload for partially updating a bin."""

    code: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        pattern=r"^[A-Za-z0-9\-_.\s]+$",
    )
    zone: str | None = Field(default=None, max_length=50)

    @field_validator("code")
    @classmethod
    def validate_and_normalize_code(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip().upper()
            if not v:
                msg = "Bin code cannot be empty."
                raise ValueError(msg)
        return v

    @field_validator("zone")
    @classmethod
    def validate_and_normalize_zone(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            return v if v else None
        return v


class BinResponse(BinBase):
    """Payload returned to the client for a single bin."""

    id: UUID
    workspace_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BinListResponse(BinResponse):
    """Bin representation for list views, including total physical stock."""

    quantity_on_hand: int = 0

    model_config = ConfigDict(from_attributes=True)


class BinPaginatedResponse(BaseModel):
    """Payload for paginated bin lists."""

    items: list[BinListResponse]
    total: int
