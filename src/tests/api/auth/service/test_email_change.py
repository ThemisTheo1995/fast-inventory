import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.auth.exceptions import (
    TokenInvalidError,
    UserExistsExceptionError,
    UserNotFoundError,
)
from erp.api.auth.models import User
from erp.api.auth.service import AuthService
from erp.core.config import get_settings

settings = get_settings()


def unique_email(prefix: str = "email_change") -> str:
    return f"{prefix}_{uuid.uuid4().hex}@example.com"


async def create_user(
    db_session: AsyncSession,
    email: str | None = None,
    last_email_change_sent_at: datetime | None = None,
) -> User:
    user = User(
        email=email or unique_email(),
        is_whitelisted=True,
        last_email_change_sent_at=last_email_change_sent_at,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def test_request_email_change_happy_path(
    db_session: AsyncSession,
):
    auth_service = AuthService(db_session)
    user = await create_user(db_session)
    new_email = unique_email("new")

    mock_provider = AsyncMock()
    mock_message = object()

    with (
        patch(
            "erp.api.auth.service.generate_email_change_token",
            return_value="email-change-token",
        ) as token_mock,
        patch(
            "erp.api.auth.service.build_email_change_email",
            return_value=mock_message,
        ) as email_builder_mock,
        patch(
            "erp.api.auth.service.get_email_provider",
            return_value=mock_provider,
        ),
    ):
        await auth_service.request_email_change(user.id, new_email)

    await db_session.refresh(user)

    assert user.last_email_change_sent_at is not None
    assert user.last_email_change_sent_at <= datetime.now(UTC)

    token_mock.assert_called_once_with(user.id, new_email)
    email_builder_mock.assert_called_once_with(
        recipient=new_email,
        token="email-change-token",
    )
    mock_provider.send_email.assert_awaited_once_with(mock_message)


async def test_request_email_change_email_already_exists(
    db_session: AsyncSession,
):
    auth_service = AuthService(db_session)

    user = await create_user(db_session)
    existing_user = await create_user(db_session)

    with (
        patch("erp.api.auth.service.get_email_provider") as provider_mock,
        pytest.raises(UserExistsExceptionError),
    ):
        await auth_service.request_email_change(
            user.id,
            existing_user.email,
        )

    provider_mock.assert_not_called()

    await db_session.refresh(user)
    assert user.last_email_change_sent_at is None


async def test_request_email_change_within_cooldown(
    db_session: AsyncSession,
):
    auth_service = AuthService(db_session)

    previous_request = datetime.now(UTC)
    user = await create_user(
        db_session,
        last_email_change_sent_at=previous_request,
    )

    with (
        patch("erp.api.auth.service.get_email_provider") as provider_mock,
        patch("erp.api.auth.service.generate_email_change_token") as token_mock,
    ):
        await auth_service.request_email_change(
            user.id,
            unique_email("new"),
        )

    provider_mock.assert_not_called()
    token_mock.assert_not_called()

    await db_session.refresh(user)
    assert user.last_email_change_sent_at == previous_request


async def test_request_email_change_after_cooldown(
    db_session: AsyncSession,
):
    auth_service = AuthService(db_session)

    previous_request = datetime.now(UTC) - timedelta(minutes=settings.CHANGE_EMAIL_COOLDOWN_MINUTES + 1)
    user = await create_user(
        db_session,
        last_email_change_sent_at=previous_request,
    )

    mock_provider = AsyncMock()

    with (
        patch(
            "erp.api.auth.service.generate_email_change_token",
            return_value="email-change-token",
        ),
        patch(
            "erp.api.auth.service.build_email_change_email",
            return_value=object(),
        ),
        patch(
            "erp.api.auth.service.get_email_provider",
            return_value=mock_provider,
        ),
    ):
        await auth_service.request_email_change(
            user.id,
            unique_email("new"),
        )

    mock_provider.send_email.assert_awaited_once()

    await db_session.refresh(user)
    assert user.last_email_change_sent_at > previous_request


async def test_confirm_email_change_happy_path(
    db_session: AsyncSession,
):
    auth_service = AuthService(db_session)

    user = await create_user(db_session)
    new_email = unique_email("confirmed")

    payload = {
        "type": "email_change",
        "sub": str(user.id),
        "new_email": new_email,
    }

    with patch(
        "erp.api.auth.service.decode_token",
        return_value=payload,
    ):
        await auth_service.confirm_email_change("valid-token")

    await db_session.refresh(user)

    assert user.email == new_email


@pytest.mark.parametrize(
    "payload",
    [
        {
            "type": "access",
            "sub": str(uuid.uuid4()),
            "new_email": unique_email("wrong_type"),
        },
        {
            "type": "email_change",
            "sub": str(uuid.uuid4()),
        },
        {
            "type": "email_change",
            "new_email": unique_email("missing_sub"),
        },
        {
            "type": "email_change",
            "sub": str(uuid.uuid4()),
            "new_email": "",
        },
    ],
)
async def test_confirm_email_change_invalid_payload(
    db_session: AsyncSession,
    payload: dict,
):
    auth_service = AuthService(db_session)

    with (
        patch(
            "erp.api.auth.service.decode_token",
            return_value=payload,
        ),
        pytest.raises(TokenInvalidError),
    ):
        await auth_service.confirm_email_change("invalid-token")


async def test_confirm_email_change_user_not_found(
    db_session: AsyncSession,
):
    auth_service = AuthService(db_session)

    payload = {
        "type": "email_change",
        "sub": str(uuid.uuid4()),
        "new_email": unique_email("not_found"),
    }

    with (
        patch(
            "erp.api.auth.service.decode_token",
            return_value=payload,
        ),
        pytest.raises(UserNotFoundError),
    ):
        await auth_service.confirm_email_change("valid-token")


async def test_confirm_email_change_invalid_token(
    db_session: AsyncSession,
):
    auth_service = AuthService(db_session)

    with (
        patch(
            "erp.api.auth.service.decode_token",
            side_effect=TokenInvalidError(),
        ),
        pytest.raises(TokenInvalidError),
    ):
        await auth_service.confirm_email_change("invalid-token")
