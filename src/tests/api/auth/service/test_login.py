import uuid
from datetime import UTC, datetime

import pytest
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.auth.exceptions import (
    CredentialsExceptionError,
    UserNotWhitelistedError,
)
from erp.api.auth.models import User, UserSession
from erp.api.auth.service import AuthService
from erp.api.auth.utils import get_password_hash
from erp.api.workspace.models import Workspace
from erp.api.workspace_user.enums import InvitationStatusEnum, WorkspaceRoleEnum
from erp.api.workspace_user.models import WorkspaceUser


async def test_login_happy_path(db_session: AsyncSession):
    auth_service = AuthService(db_session)
    raw_password = "MySuperSecretPassword"

    user = User(
        email="login_ok@example.com",
        first_name="Login",
        last_name="User",
        hashed_password=get_password_hash(raw_password),
        is_whitelisted=True,
    )
    workspace = Workspace(name="User Space", email="space@user.com")
    db_session.add_all([user, workspace])
    await db_session.flush()

    link = WorkspaceUser(
        user_id=user.id,
        workspace_id=workspace.id,
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status=InvitationStatusEnum.ACTIVE,
    )
    db_session.add(link)
    await db_session.commit()

    login_data = OAuth2PasswordRequestForm(username="login_ok@example.com", password=raw_password)

    response = await auth_service.login(login_data)

    assert response.access_token is not None
    assert response.refresh_token is not None
    assert response.workspace_id == workspace.id

    # Assert stateful active session exists (RESTORED ORIGINAL ASSERTIONS)
    res_session = await db_session.execute(select(UserSession).where(UserSession.user_id == user.id))
    session = res_session.scalar_one_or_none()
    assert session is not None


async def test_login_user_with_no_workspaces_raises_credentials_error(db_session: AsyncSession):
    """UPDATED LOGIC: Raises CredentialsExceptionError instead of IndexError for orphaned users."""
    auth_service = AuthService(db_session)
    raw_password = "corrupted_state_password"
    user = User(
        email="orphan@example.com",
        first_name="Orphaned",
        last_name="User",
        hashed_password=get_password_hash(raw_password),
        is_whitelisted=True,
    )
    db_session.add(user)
    await db_session.flush()

    login_data = OAuth2PasswordRequestForm(username="orphan@example.com", password=raw_password)

    with pytest.raises(CredentialsExceptionError):
        await auth_service.login(login_data)


@pytest.mark.parametrize(
    "email, password, has_password",
    [
        ("exists_user@example.com", "incorrect_password", True),
        ("missing_user@example.com", "any_password", True),
        ("exists_user@example.com", "", True),
        ("exists_user@example.com", "any_password", False),  # NEW LOGIC: Un-onboarded user (None password check)
    ],
)
async def test_login_exception_invalid_credentials(db_session: AsyncSession, email, password, has_password):
    auth_service = AuthService(db_session)

    pw_hash = get_password_hash("real_password") if has_password else None
    user = User(
        email="exists_user@example.com",
        first_name="Target",
        last_name="User",
        hashed_password=pw_hash,
    )
    workspace = Workspace(name="Target Space", email="target@space.com")
    db_session.add_all([user, workspace])
    await db_session.flush()

    link = WorkspaceUser(
        user_id=user.id,
        workspace_id=workspace.id,
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status=InvitationStatusEnum.ACTIVE,
    )
    db_session.add(link)
    await db_session.flush()

    login_data = OAuth2PasswordRequestForm(username=email, password=password)

    with pytest.raises(CredentialsExceptionError):
        await auth_service.login(login_data)


async def test_login_not_whitelisted_error(db_session: AsyncSession):
    auth_service = AuthService(db_session)
    email = f"black_{uuid.uuid4().hex}@test.com"

    user = User(email=email, hashed_password=get_password_hash("pass"), is_whitelisted=False)
    workspace = Workspace(name="WS", email=f"ws_{uuid.uuid4().hex}@test.com")
    db_session.add_all([user, workspace])
    await db_session.flush()

    link = WorkspaceUser(
        user_id=user.id,
        workspace_id=workspace.id,
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status=InvitationStatusEnum.ACTIVE,
    )
    db_session.add(link)
    await db_session.commit()

    login_data = OAuth2PasswordRequestForm(username=email, password="pass")
    with pytest.raises(UserNotWhitelistedError):
        await auth_service.login(login_data)


async def test_login_purges_multiple_concurrent_sessions(db_session: AsyncSession):
    """RESTORED ORIGINAL TEST: Validates strict single-session concurrency limits."""
    auth_service = AuthService(db_session)
    raw_pw = "pass123"
    user = User(
        email="purge@example.com",
        first_name="P",
        last_name="U",
        hashed_password=get_password_hash(raw_pw),
        is_whitelisted=True,
    )
    workspace = Workspace(name="Purge Corp", email="purge@corp.com")
    db_session.add_all([user, workspace])
    await db_session.flush()

    link = WorkspaceUser(
        user_id=user.id,
        workspace_id=workspace.id,
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status=InvitationStatusEnum.ACTIVE,
    )

    session_1 = UserSession(user_id=user.id, session_id="session-alpha", expires_at=datetime.now(UTC))
    session_2 = UserSession(user_id=user.id, session_id="session-beta", expires_at=datetime.now(UTC))

    db_session.add_all([link, session_1, session_2])
    await db_session.flush()

    login_data = OAuth2PasswordRequestForm(username="purge@example.com", password=raw_pw)

    response = await auth_service.login(login_data)
    assert response.workspace_id == workspace.id

    res_sessions = await db_session.execute(select(UserSession).where(UserSession.user_id == user.id))
    remaining_sessions = res_sessions.scalars().all()
    assert len(remaining_sessions) == 1
    assert remaining_sessions[0].session_id not in ["session-alpha", "session-beta"]
