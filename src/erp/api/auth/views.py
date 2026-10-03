from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.auth.schemas.user import (
    LoginResponse,
    OnboardResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    RegisterResponse,
    UserCreate,
)
from erp.api.auth.service import AuthService
from erp.core.config import get_settings
from erp.database.base import get_db

settings = get_settings()

router = APIRouter()


@router.post("/verify", status_code=status.HTTP_200_OK)
async def verify(
    token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Endpoint called when user clicks the presigned/signed URL in their email."""
    service = AuthService(db)

    await service.verify(token)

    return {"detail": "Account successfully whitelisted. You may now log in."}


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
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

    return RegisterResponse(workspace_id=result.workspace_id, is_whitelisted=result.is_whitelisted)


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

    return RegisterResponse(workspace_id=result.workspace_id, is_whitelisted=result.is_whitelisted)


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

    return LoginResponse(workspace_id=result.workspace_id, is_whitelisted=result.is_whitelisted)


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


@router.post("/request-password-reset", status_code=status.HTTP_200_OK)
async def request_password_reset(
    data: PasswordResetRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Sends a password reset link to the email provided if an account exists."""
    service = AuthService(db)

    await service.request_password_reset(data.email)

    return {"detail": "If an account with that email exists, a password reset link has been sent."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    data: PasswordResetConfirm,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Resets user password using the token sent via email and clears current session cookies."""
    service = AuthService(db)

    await service.confirm_password_reset(token=data.token, new_password=data.new_password)

    # Invalidate active browser cookies if any existed
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")

    return {"detail": "Password successfully reset. You may now log in with your new password."}
