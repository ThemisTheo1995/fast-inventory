import uuid

from pydantic import BaseModel, ConfigDict, EmailStr

from erp.api.pricing.enums import PlanName
from erp.api.workspace.schemas import WorkspaceCreate


class AuthUser(BaseModel):
    id: uuid.UUID | None = None
    role: str
    status: str


class AuthResult(BaseModel):
    access_token: str
    refresh_token: str
    workspace_id: uuid.UUID


class AuthResponse(BaseModel):
    workspace_id: uuid.UUID


# =======================================================
# REGISTER NEW WORKSPACE USER
# =======================================================


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str | None = None
    last_name: str | None = None


class OnboardResult(AuthResult):
    pass


class OnboardResponse(AuthResponse):
    pass


class RegisterResult(AuthResult):
    pass


class RegisterRequest(BaseModel):
    """Composite schema for onboarding."""

    model_config = ConfigDict(extra="forbid")

    user: UserCreate
    workspace: WorkspaceCreate
    plan: PlanName


class RegisterResponse(AuthResponse):
    pass


# =======================================================
# LOGIN WORKSPACE USER
# =======================================================


class LoginResult(AuthResult):
    pass


class LoginResponse(BaseModel):
    workspace_id: uuid.UUID
