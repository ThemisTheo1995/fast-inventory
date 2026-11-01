import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.auth.exceptions import TokenInvalidError
from erp.api.auth.models import User, UserSession
from erp.api.auth.service import AuthService
from erp.api.auth.utils import (
    create_access_token,
    decode_token,
    generate_token_pair,
)


def unique_email(prefix: str = "refresh") -> str:
    return f"{prefix}_{uuid.uuid4().hex}@example.com"


async def create_user(db_session: AsyncSession) -> User:
    user = User(
        email=unique_email(),
        first_name="Refresh",
        last_name="User",
        hashed_password="hash",
        is_whitelisted=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def get_session(
    db_session: AsyncSession,
    session_id: str,
) -> UserSession | None:
    result = await db_session.execute(select(UserSession).where(UserSession.session_id == session_id))
    return result.scalar_one_or_none()


async def test_refresh_token_happy_path(db_session: AsyncSession):
    auth_service = AuthService(db_session)
    user = await create_user(db_session)

    tokens = generate_token_pair(user.id)
    refresh_payload = decode_token(tokens["refresh_token"])

    session = UserSession(
        user_id=user.id,
        session_id=refresh_payload["jti"],
        expires_at=datetime.fromtimestamp(
            refresh_payload["exp"],
            tz=UTC,
        ),
    )
    db_session.add(session)
    await db_session.commit()

    new_access_token = await auth_service.refresh_token(tokens["refresh_token"])

    assert new_access_token

    access_payload = decode_token(new_access_token)

    assert access_payload["sub"] == str(user.id)
    assert access_payload["type"] == "access"

    # Refreshing an access token must not remove the refresh session.
    persisted_session = await get_session(
        db_session,
        refresh_payload["jti"],
    )
    assert persisted_session is not None
    assert persisted_session.user_id == user.id


async def test_refresh_token_missing_token(db_session: AsyncSession):
    auth_service = AuthService(db_session)

    with pytest.raises(TokenInvalidError):
        await auth_service.refresh_token(None)


async def test_refresh_token_decode_exception(db_session: AsyncSession):
    auth_service = AuthService(db_session)

    with (
        patch(
            "erp.api.auth.service.decode_token",
            side_effect=ValueError("Bad token data"),
        ),
        pytest.raises(TokenInvalidError),
    ):
        await auth_service.refresh_token("bad-token")


async def test_refresh_token_wrong_token_type(db_session: AsyncSession):
    auth_service = AuthService(db_session)
    access_token = create_access_token(subject=str(uuid.uuid4()))

    with pytest.raises(TokenInvalidError):
        await auth_service.refresh_token(access_token)


@pytest.mark.parametrize(
    "mock_payload",
    [
        {"type": "refresh", "jti": "missing-sub"},
        {"type": "refresh", "sub": "missing-jti"},
        {"type": "refresh"},
    ],
    ids=[
        "missing-subject",
        "missing-session-id",
        "missing-both-claims",
    ],
)
async def test_refresh_token_missing_required_claims(
    db_session: AsyncSession,
    mock_payload: dict,
):
    auth_service = AuthService(db_session)

    with (
        patch(
            "erp.api.auth.service.decode_token",
            return_value=mock_payload,
        ),
        pytest.raises(TokenInvalidError),
    ):
        await auth_service.refresh_token("mock-refresh-token")


async def test_refresh_token_missing_session_is_rejected(
    db_session: AsyncSession,
):
    auth_service = AuthService(db_session)
    user = await create_user(db_session)

    tokens = generate_token_pair(user.id)

    with pytest.raises(TokenInvalidError):
        await auth_service.refresh_token(tokens["refresh_token"])


async def test_refresh_token_unknown_user_is_rejected(
    db_session: AsyncSession,
):
    auth_service = AuthService(db_session)

    unknown_user_id = uuid.uuid4()
    tokens = generate_token_pair(unknown_user_id)

    with pytest.raises(TokenInvalidError):
        await auth_service.refresh_token(tokens["refresh_token"])


async def test_refresh_token_expired_database_session_is_deleted(
    db_session: AsyncSession,
):
    auth_service = AuthService(db_session)
    user = await create_user(db_session)

    session_id = f"expired-{uuid.uuid4().hex}"

    session = UserSession(
        user_id=user.id,
        session_id=session_id,
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(session)
    await db_session.commit()

    with (
        patch(
            "erp.api.auth.service.decode_token",
            return_value={
                "type": "refresh",
                "sub": str(user.id),
                "jti": session_id,
            },
        ),
        pytest.raises(TokenInvalidError),
    ):
        await auth_service.refresh_token("mock-refresh-token")

    assert await get_session(db_session, session_id) is None


async def test_refresh_token_does_not_delete_other_users_sessions(
    db_session: AsyncSession,
):
    auth_service = AuthService(db_session)

    user = await create_user(db_session)
    other_user = await create_user(db_session)

    session_id = f"session-{uuid.uuid4().hex}"
    other_session_id = f"other-session-{uuid.uuid4().hex}"

    db_session.add_all(
        [
            UserSession(
                user_id=user.id,
                session_id=session_id,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            ),
            UserSession(
                user_id=other_user.id,
                session_id=other_session_id,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            ),
        ]
    )
    await db_session.commit()

    with (
        patch(
            "erp.api.auth.service.decode_token",
            return_value={
                "type": "refresh",
                "sub": str(user.id),
                "jti": other_session_id,
            },
        ),
        pytest.raises(TokenInvalidError),
    ):
        await auth_service.refresh_token("mock-refresh-token")

    assert await get_session(db_session, session_id) is not None
    assert await get_session(db_session, other_session_id) is not None
