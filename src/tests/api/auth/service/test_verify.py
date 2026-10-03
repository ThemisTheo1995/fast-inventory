import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.auth.exceptions import (
    UserNotFoundError,
)
from erp.api.auth.models import User
from erp.api.auth.service import AuthService


async def test_verify_happy_path(db_session: AsyncSession):
    auth_service = AuthService(db_session)
    user = User(email="verify_me@example.com", is_whitelisted=False)
    db_session.add(user)
    await db_session.commit()

    with patch("erp.api.auth.service.decode_whitelist_user_token", return_value=user.id):
        await auth_service.verify("valid-token")

    await db_session.refresh(user)
    assert user.is_whitelisted is True


async def test_verify_already_whitelisted_is_noop(db_session: AsyncSession):
    auth_service = AuthService(db_session)
    user = User(email="already@example.com", is_whitelisted=True)
    db_session.add(user)
    await db_session.commit()

    with patch("erp.api.auth.service.decode_whitelist_user_token", return_value=user.id):
        await auth_service.verify("valid-token")

    await db_session.refresh(user)
    assert user.is_whitelisted is True  # State remains untouched


async def test_verify_user_not_found(db_session: AsyncSession):
    auth_service = AuthService(db_session)
    fake_id = str(uuid.uuid4())
    with (
        patch("erp.api.auth.service.decode_whitelist_user_token", return_value=fake_id),
        pytest.raises(UserNotFoundError),
    ):
        await auth_service.verify("valid-token")
