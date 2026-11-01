import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.auth.exceptions import TokenInvalidError, UserNotFoundError
from erp.api.auth.models import User, UserSession
from erp.api.auth.service import AuthService
from erp.api.auth.utils import (
    generate_password_reset_token,
    verify_password,
)


def unique_email(prefix: str = "password_reset") -> str:
    return f"{prefix}_{uuid.uuid4().hex}@example.com"


async def create_user(
    db_session: AsyncSession,
    *,
    email: str | None = None,
    first_name: str | None = "Test",
    hashed_password: str | None = None,
) -> User:
    user = User(
        email=email or unique_email(),
        first_name=first_name,
        last_name="User",
        hashed_password=hashed_password,
        is_whitelisted=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def get_user_sessions(
    db_session: AsyncSession,
    user_id: uuid.UUID,
) -> list[UserSession]:
    result = await db_session.execute(select(UserSession).where(UserSession.user_id == user_id))
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# REQUEST PASSWORD RESET
# ---------------------------------------------------------------------------


async def test_request_password_reset_sends_email(
    db_session: AsyncSession,
):
    user = await create_user(db_session, first_name="Jane")
    auth_service = AuthService(db_session)

    email_provider = AsyncMock()
    email_message = object()

    with (
        patch(
            "erp.api.auth.service.get_email_provider",
            return_value=email_provider,
        ),
        patch(
            "erp.api.auth.service.build_password_reset_email",
            return_value=email_message,
        ) as build_email,
    ):
        await auth_service.request_password_reset(user.email)

    build_email.assert_called_once()

    email_kwargs = build_email.call_args.kwargs
    assert email_kwargs["recipient"] == user.email
    assert email_kwargs["user_name"] == "Jane"
    assert email_kwargs["reset_token"]

    email_provider.send_email.assert_awaited_once_with(email_message)

    await db_session.refresh(user)
    assert user.last_password_reset_sent_at is not None
    assert user.last_password_reset_sent_at.tzinfo is not None


async def test_request_password_reset_unknown_email_is_silent(
    db_session: AsyncSession,
):
    auth_service = AuthService(db_session)
    email_provider = AsyncMock()

    with (
        patch(
            "erp.api.auth.service.get_email_provider",
            return_value=email_provider,
        ) as get_provider,
        patch(
            "erp.api.auth.service.build_password_reset_email",
        ) as build_email,
    ):
        result = await auth_service.request_password_reset(unique_email("unknown"))

    assert result is None
    get_provider.assert_not_called()
    build_email.assert_not_called()
    email_provider.send_email.assert_not_called()


async def test_request_password_reset_respects_cooldown(
    db_session: AsyncSession,
):
    user = await create_user(db_session)

    # A recent request should fall inside the configured cooldown.
    user.last_password_reset_sent_at = datetime.now(UTC)
    await db_session.commit()

    original_timestamp = user.last_password_reset_sent_at

    auth_service = AuthService(db_session)
    email_provider = AsyncMock()

    with (
        patch(
            "erp.api.auth.service.get_email_provider",
            return_value=email_provider,
        ) as get_provider,
        patch(
            "erp.api.auth.service.build_password_reset_email",
        ) as build_email,
    ):
        await auth_service.request_password_reset(user.email)

    await db_session.refresh(user)

    assert user.last_password_reset_sent_at == original_timestamp
    get_provider.assert_not_called()
    build_email.assert_not_called()
    email_provider.send_email.assert_not_called()


async def test_request_password_reset_uses_fallback_user_name(
    db_session: AsyncSession,
):
    user = await create_user(db_session, first_name=None)
    auth_service = AuthService(db_session)

    email_provider = AsyncMock()

    with (
        patch(
            "erp.api.auth.service.get_email_provider",
            return_value=email_provider,
        ),
        patch(
            "erp.api.auth.service.build_password_reset_email",
            return_value=object(),
        ) as build_email,
    ):
        await auth_service.request_password_reset(user.email)

    assert build_email.call_args.kwargs["user_name"] == "there"


async def test_request_password_reset_email_failure_keeps_timestamp(
    db_session: AsyncSession,
):
    user = await create_user(db_session)
    auth_service = AuthService(db_session)

    email_provider = AsyncMock()
    email_provider.send_email.side_effect = RuntimeError("Email delivery failed")

    with (
        patch(
            "erp.api.auth.service.get_email_provider",
            return_value=email_provider,
        ),
        patch(
            "erp.api.auth.service.build_password_reset_email",
            return_value=object(),
        ),
        pytest.raises(RuntimeError, match="Email delivery failed"),
    ):
        await auth_service.request_password_reset(user.email)

    # The service commits the timestamp before attempting email delivery.
    await db_session.refresh(user)
    assert user.last_password_reset_sent_at is not None


# ---------------------------------------------------------------------------
# CONFIRM PASSWORD RESET
# ---------------------------------------------------------------------------


async def test_confirm_password_reset_updates_password(
    db_session: AsyncSession,
):
    old_password = "OldPassword123!"
    new_password = "NewPassword456!"

    user = await create_user(
        db_session,
        hashed_password="",
    )

    # Set a known initial password hash.
    from erp.api.auth.utils import get_password_hash

    user.hashed_password = get_password_hash(old_password)
    await db_session.commit()

    token = generate_password_reset_token(user.id)

    auth_service = AuthService(db_session)

    await auth_service.confirm_password_reset(token, new_password)

    await db_session.refresh(user)

    assert user.hashed_password is not None
    assert verify_password(new_password, user.hashed_password)
    assert not verify_password(old_password, user.hashed_password)


async def test_confirm_password_reset_revokes_all_sessions(
    db_session: AsyncSession,
):
    user = await create_user(db_session)

    sessions = [
        UserSession(
            user_id=user.id,
            session_id=f"session-{uuid.uuid4().hex}",
            expires_at=datetime.now(UTC),
        )
        for _ in range(3)
    ]

    db_session.add_all(sessions)
    await db_session.commit()

    token = generate_password_reset_token(user.id)
    auth_service = AuthService(db_session)

    await auth_service.confirm_password_reset(
        token,
        "NewPassword456!",
    )

    remaining_sessions = await get_user_sessions(db_session, user.id)

    assert remaining_sessions == []


async def test_confirm_password_reset_user_not_found(
    db_session: AsyncSession,
):
    unknown_user_id = uuid.uuid4()
    token = generate_password_reset_token(unknown_user_id)

    auth_service = AuthService(db_session)

    with pytest.raises(UserNotFoundError):
        await auth_service.confirm_password_reset(
            token,
            "NewPassword456!",
        )


async def test_confirm_password_reset_invalid_token(
    db_session: AsyncSession,
):
    auth_service = AuthService(db_session)

    with (
        patch(
            "erp.api.auth.service.decode_password_reset_token",
            side_effect=TokenInvalidError(),
        ),
        pytest.raises(TokenInvalidError),
    ):
        await auth_service.confirm_password_reset(
            "invalid-token",
            "NewPassword456!",
        )
