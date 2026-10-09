import unicodedata
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from erp.api.workspace_user.enums import WorkspaceRoleEnum
from erp.api.workspace_user.exceptions import InvalidNameError, NameTooLongError, NameTooShortError


class WorkspaceUserInviteRequest(BaseModel):
    email: EmailStr
    role: str


class WorkspaceUserUpdateRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    is_deleted: bool | None = None
    role: WorkspaceRoleEnum | None = None
    status: str | None = None


class WorkspaceUserResponse(BaseModel):
    id: UUID | None = None
    name: str | None = None
    email: EmailStr
    role: WorkspaceRoleEnum
    status: str

    model_config = ConfigDict(from_attributes=True)


class UserUpdateRequest(BaseModel):
    first_name: str | None = Field(default=None, min_length=2, max_length=50)
    last_name: str | None = Field(default=None, min_length=2, max_length=50)
    email: EmailStr | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return value

        value = value.strip()

        if len(value) < 2:
            raise NameTooShortError()

        if len(value) > 50:
            raise NameTooLongError()

        if not all(unicodedata.category(char).startswith("L") or char in " -'" or char == "\u2019" for char in value):
            raise InvalidNameError()

        if not any(unicodedata.category(char).startswith("L") for char in value):
            raise NameTooShortError()

        return value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    first_name: str | None
    last_name: str | None
