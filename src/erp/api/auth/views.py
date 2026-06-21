from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from erp.api.auth.schemas import (
    LogoutRequest,
    OnboardRequest,
    RefreshResponse,
    RefreshToken,
    RegisterRequest,
    TokenResponse,
)
from erp.api.auth.service import AuthService
from erp.database.base import get_db

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:

    service = AuthService(db)

    return service.register(data)


@router.post("/onboard", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def onboard(data: OnboardRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    """Finalises profiles for users invited to an existing workspace."""

    service = AuthService(db)

    return service.onboard(data)


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Annotated[Session, Depends(get_db)]
) -> TokenResponse:

    service = AuthService(db)

    return service.login(form_data)


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(data: LogoutRequest, db: Annotated[Session, Depends(get_db)]) -> dict:

    service = AuthService(db)

    service.logout(data)

    return {"detail": "Successfully logged out"}


@router.post("/refresh", response_model=RefreshResponse, status_code=status.HTTP_200_OK)
def refresh_token_endpoint(data: RefreshToken, db: Annotated[Session, Depends(get_db)]) -> RefreshResponse:
    service = AuthService(db)

    return service.refresh_token(data)
