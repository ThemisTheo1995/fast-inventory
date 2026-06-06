from pydantic import BaseModel, ConfigDict, EmailStr


class WorkspaceCreate(BaseModel):
    name: str
    email: EmailStr


class WorkspaceMemberResponse(BaseModel):
    id: str
    name: str | None = None
    email: EmailStr
    role_id: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role_id: str


class UpdateRoleRequest(BaseModel):
    role_id: str
