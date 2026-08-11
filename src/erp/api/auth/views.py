from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from src.erp.api.auth.schemas.user import (
    LoginResponse,
    OnboardResponse,
    RegisterRequest,
    RegisterResponse,
    UserCreate,
)
from src.erp.api.auth.service import AuthService
from src.erp.core.config import get_settings
from src.erp.database.base import get_db

settings = get_settings()

router = APIRouter()


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, response: Response, db: Annotated[Session, Depends(get_db)]) -> RegisterResponse:

    service = AuthService(db)

    result = service.register(data)

    response.set_cookie(
        key="access_token",
        value=result.access_token,
        httponly=True,
        secure=bool(settings.COOKIE_SECURE),
        samesite="none",
    )

    response.set_cookie(
        key="refresh_token",
        value=result.refresh_token,
        httponly=True,
        secure=bool(settings.COOKIE_SECURE),
        samesite="none",
    )

    return RegisterResponse(workspace_id=result.workspace_id)


@router.post("/onboard", response_model=OnboardResponse, status_code=status.HTTP_200_OK)
def onboard(
    data: UserCreate,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> OnboardResponse:
    """Finalises profiles for users invited to an existing workspace."""

    service = AuthService(db)

    result = service.onboard(data)

    response.set_cookie(
        key="access_token",
        value=result.access_token,
        httponly=True,
        secure=bool(settings.COOKIE_SECURE),
        samesite="none",
    )

    response.set_cookie(
        key="refresh_token",
        value=result.refresh_token,
        httponly=True,
        secure=bool(settings.COOKIE_SECURE),
        samesite="none",
    )

    return OnboardResponse(
        workspace_id=result.workspace_id,
    )


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
def login(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> LoginResponse:

    service = AuthService(db)

    result = service.login(form_data)

    response.set_cookie(
        key="access_token",
        value=result.access_token,
        httponly=True,
        secure=bool(settings.COOKIE_SECURE),
        samesite="none",
    )

    response.set_cookie(
        key="refresh_token",
        value=result.refresh_token,
        httponly=True,
        secure=bool(settings.COOKIE_SECURE),
        samesite="none",
    )

    return LoginResponse(workspace_id=result.workspace_id)


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> dict:
    service = AuthService(db)

    if refresh_token:
        service.logout(refresh_token)

    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")

    return {"detail": "Successfully logged out"}


@router.post("/refresh", status_code=status.HTTP_200_OK)
def refresh_token(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> dict:
    service = AuthService(db)

    access_token = service.refresh_token(refresh_token)

    response.set_cookie(
        key="access_token", value=access_token, httponly=True, secure=bool(settings.COOKIE_SECURE), samesite="none"
    )

    return {"detail": "Access token refreshed"}
