import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.auth.models import User, UserSession
from erp.api.auth.service import AuthService
from erp.api.auth.utils import decode_token, generate_token_pair


async def create_user_with_sessions(
    db_session: AsyncSession,
    session_ids: list[str],
) -> User:
    user = User(
        email=f"logout_{uuid.uuid4().hex}@example.com",
        first_name="Logout",
        last_name="User",
        hashed_password="hash",
        is_whitelisted=True,
    )
    db_session.add(user)
    await db_session.flush()

    sessions = [
        UserSession(
            user_id=user.id,
            session_id=session_id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        for session_id in session_ids
    ]
    db_session.add_all(sessions)
    await db_session.commit()

    return user


async def get_user_sessions(
    db_session: AsyncSession,
    user_id: uuid.UUID,
) -> list[UserSession]:
    result = await db_session.execute(select(UserSession).where(UserSession.user_id == user_id))
    return list(result.scalars().all())


async def test_logout_happy_path(db_session: AsyncSession):
    auth_service = AuthService(db_session)

    user = await create_user_with_sessions(db_session, [])

    tokens = generate_token_pair(user.id)
    payload = decode_token(tokens["refresh_token"])

    session = UserSession(
        user_id=user.id,
        session_id=payload["jti"],
        expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
    )
    db_session.add(session)
    await db_session.commit()

    await auth_service.logout(tokens["refresh_token"])

    remaining_sessions = await get_user_sessions(db_session, user.id)

    assert remaining_sessions == []


async def test_logout_revoke_all_deletes_all_user_sessions(
    db_session: AsyncSession,
):
    session_ids = [
        f"session-{uuid.uuid4().hex}",
        f"session-{uuid.uuid4().hex}",
    ]
    user = await create_user_with_sessions(db_session, session_ids)

    auth_service = AuthService(db_session)

    with patch(
        "erp.api.auth.service.decode_token",
        return_value={"sub": str(user.id), "jti": session_ids[0]},
    ):
        await auth_service.logout("mock-refresh-token", revoke_all=True)

    assert await get_user_sessions(db_session, user.id) == []


async def test_logout_revoke_current_session_only(
    db_session: AsyncSession,
):
    session_ids = [
        f"session-{uuid.uuid4().hex}",
        f"session-{uuid.uuid4().hex}",
    ]
    user = await create_user_with_sessions(db_session, session_ids)

    auth_service = AuthService(db_session)

    with patch(
        "erp.api.auth.service.decode_token",
        return_value={"sub": str(user.id), "jti": session_ids[0]},
    ):
        await auth_service.logout("mock-refresh-token", revoke_all=False)

    remaining_sessions = await get_user_sessions(db_session, user.id)

    assert len(remaining_sessions) == 1
    assert remaining_sessions[0].session_id == session_ids[1]


async def test_logout_missing_session_id_revokes_all_sessions(
    db_session: AsyncSession,
):
    user = await create_user_with_sessions(
        db_session,
        [
            f"session-{uuid.uuid4().hex}",
            f"session-{uuid.uuid4().hex}",
        ],
    )

    auth_service = AuthService(db_session)

    with patch(
        "erp.api.auth.service.decode_token",
        return_value={"sub": str(user.id)},
    ):
        await auth_service.logout("mock-refresh-token", revoke_all=False)

    assert await get_user_sessions(db_session, user.id) == []


async def test_logout_missing_user_id_does_not_delete_sessions(
    db_session: AsyncSession,
):
    session_ids = [
        f"session-{uuid.uuid4().hex}",
        f"session-{uuid.uuid4().hex}",
    ]
    user = await create_user_with_sessions(db_session, session_ids)

    auth_service = AuthService(db_session)

    with patch(
        "erp.api.auth.service.decode_token",
        return_value={"type": "refresh", "jti": session_ids[0]},
    ):
        await auth_service.logout("mock-refresh-token")

    remaining_sessions = await get_user_sessions(db_session, user.id)

    assert {session.session_id for session in remaining_sessions} == set(session_ids)


async def test_logout_swallows_token_decoding_exception(
    db_session: AsyncSession,
):
    auth_service = AuthService(db_session)

    with patch(
        "erp.api.auth.service.decode_token",
        side_effect=Exception("Invalid token"),
    ):
        await auth_service.logout("invalid-token")

    # The service intentionally suppresses decoding exceptions.


async def test_logout_swallows_database_exception(
    db_session: AsyncSession,
):
    auth_service = AuthService(db_session)

    with (
        patch(
            "erp.api.auth.service.decode_token",
            return_value={"sub": str(uuid.uuid4()), "jti": "session-id"},
        ),
        patch.object(
            db_session,
            "execute",
            side_effect=Exception("DB Failure"),
        ),
        patch.object(
            db_session,
            "rollback",
            wraps=db_session.rollback,
        ) as rollback_mock,
    ):
        await auth_service.logout("mock-refresh-token")

    rollback_mock.assert_awaited_once()
