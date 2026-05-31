from pydantic import BaseModel, EmailStr


class WorkspaceMemberResponse(BaseModel):
    id: str
    name: str | None = None
    email: EmailStr
    role_id: str
    status: str

    class Config:
        from_attributes = True


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role_id: str


class UpdateRoleRequest(BaseModel):
    role_id: str
