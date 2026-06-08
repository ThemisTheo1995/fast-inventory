import uuid

from pydantic import BaseModel, ConfigDict, EmailStr

from erp.api.workspace.schemas.workspace import WorkspaceCreate


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str | None = None
    last_name: str | None = None


class RegisterRequest(BaseModel):
    """
    Composite schema used for onboarding:
    creates User + Workspace + WorkspaceUser link.
    """
    model_config = ConfigDict(extra="forbid")

    user: UserCreate
    workspace: WorkspaceCreate


class RegisterResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    workspace_id: uuid.UUID


class TokenRefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
