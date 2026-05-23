import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext

from erp.api.auth.exceptions import TokenExpiredError, TokenInvalidError
from erp.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """
    Creates a short-lived JSON Web Token for API access.
    """
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.AUTH_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "exp": expire,
        "iat": datetime.now(UTC),
        "sub": str(subject),
        "type": "access"
    }

    return jwt.encode(to_encode, settings.AUTH_SECRET_KEY, algorithm=settings.AUTH_ALGORITHM)


def create_refresh_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """
    Creates a long-lived JSON Web Token used specifically to get new access tokens.
    Includes a unique 'jti' (JWT ID) to allow for token revocation tracking in the database.
    """
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(days=settings.AUTH_REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "exp": expire,
        "iat": datetime.now(UTC),
        "sub": str(subject),
        "type": "refresh",
        "jti": str(uuid.uuid4())  # Unique identifier for the token
    }

    return jwt.encode(to_encode, settings.AUTH_SECRET_KEY, algorithm=settings.AUTH_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decodes and verifies a JWT.
    Raises custom exceptions that you can catch in your FastAPI exception handlers.
    """
    try:
        return jwt.decode(token, settings.AUTH_SECRET_KEY, algorithms=[settings.AUTH_ALGORITHM])

    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError from e

    except jwt.InvalidTokenError as e:
        raise TokenInvalidError from e


def refresh_access_token(refresh_token: str) -> str:
    """
    Validates a refresh token and issues a new access token.
    """
    # Decode and verify the refresh token
    payload = decode_token(refresh_token)

    # Ensure the token is actually a refresh token
    if payload.get("type") != "refresh":
        raise TokenInvalidError()

    # Extract the subject (user ID)
    subject = payload.get("sub")
    if not subject:
        raise TokenInvalidError()

    # Issue a new access token
    return create_access_token(subject=subject)


def generate_token_pair(subject: str) -> dict[str, str]:
    """
    Method to generate both tokens at login/registration.
    """
    return {
        "access_token": create_access_token(subject),
        "refresh_token": create_refresh_token(subject),
        "token_type": "bearer"
    }
