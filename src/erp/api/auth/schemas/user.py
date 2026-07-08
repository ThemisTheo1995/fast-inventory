import uuid

from pydantic import BaseModel, ConfigDict, EmailStr

from src.erp.api.pricing.enums import PlanName
from src.erp.api.workspace.schemas import WorkspaceCreate

# =======================================================
# REGISTER NEW WORKSPACE USER
# =======================================================


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str | None = None
    last_name: str | None = None


class RegisterRequest(BaseModel):
    """Composite schema for onboarding."""

    model_config = ConfigDict(extra="forbid")

    user: UserCreate
    workspace: WorkspaceCreate
    plan: PlanName


# =======================================================
# LOGIN WORKSPACE USER
# =======================================================


class TokenUser(BaseModel):
    id: uuid.UUID | None = None
    role: str
    status: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    workspace_id: uuid.UUID
    user: TokenUser


class RefreshToken(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ===================================
# LOGOUT WORKSPACE USER
# ===================================


class LogoutRequest(BaseModel):
    refresh_token: str
