from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from erp.api.workspace_user.enums import WorkspaceRoleEnum


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
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    first_name: str | None
    last_name: str | None
