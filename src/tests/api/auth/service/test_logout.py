import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.erp.api.auth.models import User, UserSession
from src.erp.api.auth.service import AuthService
from src.erp.api.auth.utils import decode_token, generate_token_pair


async def test_logout_happy_path(db_session: AsyncSession):
    auth_service = AuthService(db_session)

    user = User(
        email="logout_target@example.com", first_name="L", last_name="O", hashed_password="hash", is_whitelisted=True
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

    await auth_service.logout(tokens["refresh_token"])

    db_session.expire_all()

    # RESTORED ORIGINAL ASSERTION
    res_session = await db_session.execute(select(UserSession).where(UserSession.session_id == payload["jti"]))
    assert res_session.scalar_one_or_none() is None


async def test_logout_revoke_all_or_missing_session_id(db_session: AsyncSession):
    auth_service = AuthService(db_session)

    user = User(email=f"revoke_{uuid.uuid4().hex}@test.com", first_name="u", last_name="1")
    db_session.add(user)
    await db_session.flush()

    s1 = UserSession(user_id=user.id, session_id="s1", expires_at=datetime.now(UTC) + timedelta(hours=1))
    s2 = UserSession(user_id=user.id, session_id="s2", expires_at=datetime.now(UTC) + timedelta(hours=1))
    db_session.add_all([s1, s2])
    await db_session.commit()

    with patch("src.erp.api.auth.service.decode_token", return_value={"sub": str(user.id)}):
        await auth_service.logout("token")

    res = await db_session.execute(select(UserSession).where(UserSession.user_id == user.id))
    assert len(res.scalars().all()) == 0


async def test_logout_edge_case_token_missing_claims(db_session: AsyncSession):
    """RESTORED ORIGINAL TEST."""
    auth_service = AuthService(db_session)
    with patch("src.erp.api.auth.service.decode_token", return_value={"type": "refresh"}):
        # Should not raise (missing sub -> early return)
        await auth_service.logout("invalid-token-missing-claims")


async def test_logout_silently_swallows_decoding_exceptions(db_session: AsyncSession):
    """RESTORED ORIGINAL TEST."""
    auth_service = AuthService(db_session)
    with patch("src.erp.api.auth.service.decode_token", side_effect=Exception("Invalid token")):
        try:
            await auth_service.logout("complete-garbage-token-string")
        except Exception as e:
            pytest.fail(f"Logout service leaked an exception path! Error: {e}")


@patch.object(AsyncSession, "execute", side_effect=Exception("DB Failure"))
async def test_logout_db_exception_triggers_rollback(_mock_execute, db_session: AsyncSession):
    """NEW LOGIC: Covers the internal DB try/except rollback block."""
    auth_service = AuthService(db_session)
    with patch("src.erp.api.auth.service.decode_token", return_value={"sub": "u1", "jti": "s1"}):
        try:
            await auth_service.logout("token")
        except Exception:
            pytest.fail("Logout should swallow DB exceptions and rollback cleanly.")
