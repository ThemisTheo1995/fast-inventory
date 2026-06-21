import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from erp.api.workspace.schemas.workspace import WorkspaceCreate

# =======================================================
# REGISTER NEW WORKSPACE USER
# =======================================================


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


# =======================================================
# ONBOARD WORKSPACE USER
# =======================================================


class OnboardRequest(BaseModel):
    email: EmailStr = Field(..., description="The email address that received the workspace invitation.")
    password: str = Field(..., min_length=8, description="The password chosen by the user.")
    first_name: str = Field(..., min_length=1, description="The user's first name.")
    last_name: str = Field(..., min_length=1, description="The user's last name.")
