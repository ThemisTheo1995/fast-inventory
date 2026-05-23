from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from erp.api.auth.schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenRefreshResponse,
    TokenResponse,
)
from erp.api.auth.service import AuthService
from erp.api.workspace.models import WorkspaceUser
from erp.database.base import get_db

router = APIRouter()


@router.post("/register", response_model=RegisterResponse)
def register(
    data: RegisterRequest,
    db: Annotated[Session, Depends(get_db)]
) -> WorkspaceUser:

    service = AuthService(db)

    return service.onboard(data)


@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    db: Annotated[Session, Depends(get_db)]
) -> TokenResponse:

    service = AuthService(db)

    return service.login(data)


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    data: LogoutRequest,
    db: Annotated[Session, Depends(get_db)]
) -> dict:

    service = AuthService(db)

    service.logout(data)

    return {"detail": "Successfully logged out"}


@router.post("/refresh", response_model=TokenRefreshResponse)
def refresh_token_endpoint(
    data: RefreshRequest,
    db: Annotated[Session, Depends(get_db)]
) -> TokenRefreshResponse:
    service = AuthService(db)

    return service.refresh_token(data.refresh_token)
