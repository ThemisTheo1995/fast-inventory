import uuid
from datetime import UTC, datetime

import pytest
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.auth.exceptions import (
    CredentialsExceptionError,
    UserNotWhitelistedError,
)
from erp.api.auth.models import User, UserSession
from erp.api.auth.service import AuthService
from erp.api.auth.utils import decode_token, get_password_hash
from erp.api.workspace.models import Workspace
from erp.api.workspace_user.enums import InvitationStatusEnum, WorkspaceRoleEnum
from erp.api.workspace_user.models import WorkspaceUser


def unique_email(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}@example.com"


async def create_login_user(
    db_session: AsyncSession,
    *,
    email: str | None = None,
    password: str | None = "MySuperSecretPassword",
    is_whitelisted: bool = True,
    with_workspace: bool = True,
) -> tuple[User, Workspace | None]:
    """Create a user and optionally associate them with a workspace."""
    user = User(
        email=email or unique_email("login"),
        first_name="Login",
        last_name="User",
        hashed_password=get_password_hash(password) if password is not None else None,
        is_whitelisted=is_whitelisted,
    )
    db_session.add(user)

    workspace = None
    if with_workspace:
        workspace = Workspace(
            name=f"Workspace {uuid.uuid4().hex[:8]}",
            email=unique_email("workspace"),
        )
        db_session.add(workspace)
        await db_session.flush()

        membership = WorkspaceUser(
            user_id=user.id,
            workspace_id=workspace.id,
            role=WorkspaceRoleEnum.FULL_ADMIN,
            status=InvitationStatusEnum.ACTIVE,
        )
        db_session.add(membership)

    await db_session.commit()
    await db_session.refresh(user)

    return user, workspace


async def count_user_sessions(
    db_session: AsyncSession,
    user_id: uuid.UUID,
) -> int:
    result = await db_session.execute(select(func.count(UserSession.id)).where(UserSession.user_id == user_id))
    return result.scalar_one()


async def test_login_happy_path(db_session: AsyncSession):
    user, workspace = await create_login_user(db_session)
    assert workspace is not None

    auth_service = AuthService(db_session)
    raw_password = "MySuperSecretPassword"

    login_data = OAuth2PasswordRequestForm(
        username=user.email,
        password=raw_password,
    )

    response = await auth_service.login(login_data)

    assert response.access_token
    assert response.refresh_token
    assert response.workspace_id == workspace.id
    assert response.is_whitelisted is True

    access_payload = decode_token(response.access_token)
    refresh_payload = decode_token(response.refresh_token)

    assert access_payload["sub"] == str(user.id)
    assert access_payload["type"] == "access"

    assert refresh_payload["sub"] == str(user.id)
    assert refresh_payload["type"] == "refresh"
    assert refresh_payload["jti"]

    result = await db_session.execute(select(UserSession).where(UserSession.user_id == user.id))
    session = result.scalar_one()

    assert session.session_id == refresh_payload["jti"]
    assert session.expires_at == datetime.fromtimestamp(
        refresh_payload["exp"],
        tz=UTC,
    )


async def test_login_user_with_no_workspaces_raises_credentials_error(
    db_session: AsyncSession,
):
    user, _ = await create_login_user(
        db_session,
        with_workspace=False,
    )

    auth_service = AuthService(db_session)
    login_data = OAuth2PasswordRequestForm(
        username=user.email,
        password="MySuperSecretPassword",
    )

    with pytest.raises(CredentialsExceptionError):
        await auth_service.login(login_data)

    assert await count_user_sessions(db_session, user.id) == 0


@pytest.mark.parametrize(
    ("email_exists", "password", "stored_password"),
    [
        (True, "incorrect_password", "MySuperSecretPassword"),
        (False, "any_password", "MySuperSecretPassword"),
        (True, "", "MySuperSecretPassword"),
        (True, "any_password", None),
    ],
    ids=[
        "incorrect-password",
        "unknown-user",
        "empty-password",
        "user-without-password",
    ],
)
async def test_login_invalid_credentials(
    db_session: AsyncSession,
    email_exists: bool,
    password: str,
    stored_password: str | None,
):
    email = unique_email("login")

    user = None
    if email_exists:
        user, _ = await create_login_user(
            db_session,
            email=email,
            password=stored_password,
        )

    auth_service = AuthService(db_session)
    login_data = OAuth2PasswordRequestForm(
        username=email,
        password=password,
    )

    with pytest.raises(CredentialsExceptionError):
        await auth_service.login(login_data)

    if user is not None:
        assert await count_user_sessions(db_session, user.id) == 0


async def test_login_not_whitelisted_error(db_session: AsyncSession):
    user, _ = await create_login_user(
        db_session,
        is_whitelisted=False,
    )

    auth_service = AuthService(db_session)
    login_data = OAuth2PasswordRequestForm(
        username=user.email,
        password="MySuperSecretPassword",
    )

    with pytest.raises(UserNotWhitelistedError):
        await auth_service.login(login_data)

    assert await count_user_sessions(db_session, user.id) == 0


async def test_login_replaces_existing_sessions(db_session: AsyncSession):
    user, workspace = await create_login_user(db_session)
    assert workspace is not None

    old_sessions = [
        UserSession(
            user_id=user.id,
            session_id=f"old-session-{uuid.uuid4().hex}",
            expires_at=datetime.now(UTC),
        )
        for _ in range(2)
    ]

    db_session.add_all(old_sessions)
    await db_session.commit()

    auth_service = AuthService(db_session)
    login_data = OAuth2PasswordRequestForm(
        username=user.email,
        password="MySuperSecretPassword",
    )

    response = await auth_service.login(login_data)

    assert response.workspace_id == workspace.id

    result = await db_session.execute(select(UserSession).where(UserSession.user_id == user.id))
    remaining_sessions = result.scalars().all()

    assert len(remaining_sessions) == 1
    assert remaining_sessions[0].session_id not in {session.session_id for session in old_sessions}

    refresh_payload = decode_token(response.refresh_token)
    assert remaining_sessions[0].session_id == refresh_payload["jti"]


async def test_login_creates_only_one_session_per_login(
    db_session: AsyncSession,
):
    user, workspace = await create_login_user(db_session)
    assert workspace is not None

    auth_service = AuthService(db_session)

    first_login = OAuth2PasswordRequestForm(
        username=user.email,
        password="MySuperSecretPassword",
    )
    await auth_service.login(first_login)

    assert await count_user_sessions(db_session, user.id) == 1

    second_login = OAuth2PasswordRequestForm(
        username=user.email,
        password="MySuperSecretPassword",
    )
    second_response = await auth_service.login(second_login)

    assert await count_user_sessions(db_session, user.id) == 1

    result = await db_session.execute(select(UserSession).where(UserSession.user_id == user.id))
    session = result.scalar_one()

    refresh_payload = decode_token(second_response.refresh_token)
    assert session.session_id == refresh_payload["jti"]
