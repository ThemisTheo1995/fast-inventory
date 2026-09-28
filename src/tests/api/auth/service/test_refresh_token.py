import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.erp.api.auth.exceptions import (
    TokenInvalidError,
)
from src.erp.api.auth.models import User, UserSession
from src.erp.api.auth.service import AuthService
from src.erp.api.auth.utils import create_access_token, decode_token, generate_token_pair


async def test_refresh_token_happy_path(db_session: AsyncSession):
    auth_service = AuthService(db_session)
    user = User(
        email="refresh_me@example.com", first_name="R", last_name="M", hashed_password="hash", is_whitelisted=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    tokens = generate_token_pair(user.id)
    payload = decode_token(tokens["refresh_token"])

    session = UserSession(
        user_id=user.id,
        session_id=payload["jti"],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(session)
    await db_session.commit()

    new_access_token = await auth_service.refresh_token(tokens["refresh_token"])
    assert new_access_token is not None


async def test_refresh_token_decode_exception(db_session: AsyncSession):
    """NEW LOGIC: Explicit wrap around JWT decode failure."""
    auth_service = AuthService(db_session)
    with (
        patch("src.erp.api.auth.service.decode_token", side_effect=ValueError("Bad token data")),
        pytest.raises(TokenInvalidError),
    ):
        await auth_service.refresh_token("bad_token_string")


async def test_refresh_token_exception_wrong_token_type(db_session: AsyncSession):
    auth_service = AuthService(db_session)
    access_token = create_access_token(subject="user_123")
    with pytest.raises(TokenInvalidError):
        await auth_service.refresh_token(access_token)


@pytest.mark.parametrize(
    "mock_payload",
    [
        {"type": "refresh", "jti": "missing-sub"},
        {"type": "refresh", "sub": "missing-jti"},
        {"type": "refresh"},
    ],
)
async def test_refresh_token_exception_missing_required_claims(db_session: AsyncSession, mock_payload):
    auth_service = AuthService(db_session)
    with (
        patch("src.erp.api.auth.service.decode_token", return_value=mock_payload),
        pytest.raises(TokenInvalidError),
    ):
        await auth_service.refresh_token("valid.token.payload")


async def test_refresh_token_exception_session_revoked_or_overwritten(db_session: AsyncSession):
    auth_service = AuthService(db_session)
    user = User(
        email="stale_session@example.com", first_name="S", last_name="S", hashed_password="hash", is_whitelisted=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    tokens = generate_token_pair(user.id)

    with pytest.raises(TokenInvalidError):
        await auth_service.refresh_token(tokens["refresh_token"])


async def test_refresh_token_session_expired_in_db(db_session: AsyncSession):
    auth_service = AuthService(db_session)

    user = User(email=f"expired_{uuid.uuid4().hex}@test.com", first_name="e", last_name="x")
    db_session.add(user)
    await db_session.flush()

    session = UserSession(user_id=user.id, session_id="s1", expires_at=datetime.now(UTC) - timedelta(hours=1))
    db_session.add(session)
    await db_session.commit()

    with (
        patch(
            "src.erp.api.auth.service.decode_token", return_value={"type": "refresh", "sub": str(user.id), "jti": "s1"}
        ),
        pytest.raises(TokenInvalidError),
    ):
        await auth_service.refresh_token("token")

    res = await db_session.execute(select(UserSession).where(UserSession.session_id == "s1"))
    assert res.scalar_one_or_none() is None
