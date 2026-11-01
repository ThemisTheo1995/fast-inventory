import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.auth.exceptions import TokenInvalidError, UserNotFoundError
from erp.api.auth.models import User
from erp.api.auth.service import AuthService


def unique_email(prefix: str = "verify") -> str:
    return f"{prefix}_{uuid.uuid4().hex}@example.com"


async def test_verify_happy_path(db_session: AsyncSession):
    auth_service = AuthService(db_session)

    user = User(
        email=unique_email(),
        is_whitelisted=False,
    )
    db_session.add(user)
    await db_session.commit()

    with patch(
        "erp.api.auth.service.decode_whitelist_user_token",
        return_value=user.id,
    ):
        await auth_service.verify("valid-token")

    await db_session.refresh(user)

    assert user.is_whitelisted is True


async def test_verify_already_whitelisted_is_noop(
    db_session: AsyncSession,
):
    auth_service = AuthService(db_session)

    user = User(
        email=unique_email("already"),
        is_whitelisted=True,
    )
    db_session.add(user)
    await db_session.commit()

    with (
        patch(
            "erp.api.auth.service.decode_whitelist_user_token",
            return_value=user.id,
        ),
        patch.object(db_session, "commit", wraps=db_session.commit) as commit_mock,
    ):
        await auth_service.verify("valid-token")

    await db_session.refresh(user)

    assert user.is_whitelisted is True
    commit_mock.assert_not_awaited()


async def test_verify_user_not_found(db_session: AsyncSession):
    auth_service = AuthService(db_session)
    fake_id = uuid.uuid4()

    with (
        patch(
            "erp.api.auth.service.decode_whitelist_user_token",
            return_value=fake_id,
        ),
        pytest.raises(UserNotFoundError),
    ):
        await auth_service.verify("valid-token")


async def test_verify_invalid_token(db_session: AsyncSession):
    auth_service = AuthService(db_session)

    with (
        patch(
            "erp.api.auth.service.decode_whitelist_user_token",
            side_effect=TokenInvalidError(),
        ),
        pytest.raises(TokenInvalidError),
    ):
        await auth_service.verify("invalid-token")
