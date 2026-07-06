from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class WorkspaceUserInviteRequest(BaseModel):
    email: EmailStr
    role: str


class WorkspaceUserUpdateRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    is_deleted: bool | None = None
    role: str | None = None
    status: str | None = None


class WorkspaceUserResponse(BaseModel):
    id: UUID | None = None
    name: str | None = None
    email: EmailStr
    role: str
    status: str

    model_config = ConfigDict(from_attributes=True)
