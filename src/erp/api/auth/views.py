from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

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
async def register(
    data: RegisterRequest, response: Response, db: Annotated[AsyncSession, Depends(get_db)]
) -> RegisterResponse:

    service = AuthService(db)

    result = await service.register(data)

    response.set_cookie(
        key="access_token",
        value=result.access_token,
        httponly=True,
        secure=bool(settings.COOKIE_SECURE),
        samesite="lax",
    )

    response.set_cookie(
        key="refresh_token",
        value=result.refresh_token,
        httponly=True,
        secure=bool(settings.COOKIE_SECURE),
        samesite="lax",
    )

    return RegisterResponse(workspace_id=result.workspace_id)


@router.post("/onboard", response_model=OnboardResponse, status_code=status.HTTP_200_OK)
async def onboard(
    data: UserCreate,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OnboardResponse:
    """Finalises profiles for users invited to an existing workspace."""

    service = AuthService(db)

    result = await service.onboard(data)

    response.set_cookie(
        key="access_token",
        value=result.access_token,
        httponly=True,
        secure=bool(settings.COOKIE_SECURE),
        samesite="lax",
    )

    response.set_cookie(
        key="refresh_token",
        value=result.refresh_token,
        httponly=True,
        secure=bool(settings.COOKIE_SECURE),
        samesite="lax",
    )

    return OnboardResponse(
        workspace_id=result.workspace_id,
    )


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:

    service = AuthService(db)

    result = await service.login(form_data)

    response.set_cookie(
        key="access_token",
        value=result.access_token,
        httponly=True,
        secure=bool(settings.COOKIE_SECURE),
        samesite="lax",
    )

    response.set_cookie(
        key="refresh_token",
        value=result.refresh_token,
        httponly=True,
        secure=bool(settings.COOKIE_SECURE),
        samesite="lax",
    )

    return LoginResponse(workspace_id=result.workspace_id)


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> dict:

    service = AuthService(db)

    if refresh_token:
        await service.logout(refresh_token)

    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")

    return {"detail": "Successfully logged out"}


@router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh_token(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> dict:

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing or blocked by browser",
        )

    service = AuthService(db)

    access_token = await service.refresh_token(refresh_token)

    response.set_cookie(
        key="access_token", value=access_token, httponly=True, secure=bool(settings.COOKIE_SECURE), samesite="lax"
    )

    return {"detail": "Access token refreshed"}
