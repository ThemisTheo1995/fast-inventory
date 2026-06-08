from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class WorkspaceCreate(BaseModel):
    name: str
    email: EmailStr


class WorkspaceUserResponse(BaseModel):
    id: UUID
    name: str | None = None
    email: EmailStr
    role_id: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class InviteWorkspaceUserRequest(BaseModel):
    email: EmailStr
    role_id: str


class UpdateWorkspaceUserRoleRequest(BaseModel):
    role_id: str
