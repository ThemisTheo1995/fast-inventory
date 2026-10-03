import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.auth.exceptions import (
    AccountAlreadyOnboardedExceptionError,
    InvitationNotFoundExceptionError,
    OnboardingFailedExceptionError,
)
from erp.api.auth.models import User
from erp.api.auth.schemas.user import UserCreate
from erp.api.auth.service import AuthService
from erp.api.workspace.models import Workspace
from erp.api.workspace_user.enums import InvitationStatusEnum, WorkspaceRoleEnum
from erp.api.workspace_user.models import WorkspaceUser


@patch("erp.api.auth.service.get_email_provider")
async def test_onboard_happy_path(mock_get_email, db_session: AsyncSession):
    auth_service = AuthService(db_session)
    mock_email_provider = AsyncMock()
    mock_get_email.return_value = mock_email_provider

    user = User(email="invitee@test.com", first_name=None, last_name=None, is_whitelisted=True, hashed_password=None)
    workspace = Workspace(name="Invite Workspace", email="ws@test.com")
    db_session.add_all([user, workspace])
    await db_session.flush()

    link = WorkspaceUser(
        user_id=user.id,
        workspace_id=workspace.id,
        role=WorkspaceRoleEnum.EDIT_ONLY,
        status=InvitationStatusEnum.PENDING.value,
        is_deleted=False,
    )
    db_session.add(link)
    await db_session.commit()

    data = UserCreate(email="invitee@test.com", password="NewPassword123", first_name="Jane", last_name="Doe")
    result = await auth_service.onboard(data)

    # RESTORED ORIGINAL ASSERTIONS
    assert result.access_token is not None
    assert result.workspace_id == workspace.id

    await db_session.refresh(user)
    await db_session.refresh(link)

    assert user.first_name == "Jane"
    assert user.hashed_password is not None
    assert link.status == InvitationStatusEnum.ACTIVE.value

    # Whitelisted users don't get verification email in onboarding
    mock_email_provider.send_email.assert_not_called()


@patch("erp.api.auth.service.get_email_provider")
async def test_onboard_unwhitelisted_user_sends_email(mock_get_email, db_session: AsyncSession):
    mock_email_provider = AsyncMock()
    mock_get_email.return_value = mock_email_provider

    auth_service = AuthService(db_session)
    email = f"unverified_{uuid.uuid4().hex}@test.com"

    user = User(email=email, is_whitelisted=False)
    workspace = Workspace(name="Invite Workspace", email=f"ws_{uuid.uuid4().hex}@test.com")
    db_session.add_all([user, workspace])
    await db_session.flush()

    link = WorkspaceUser(
        user_id=user.id,
        workspace_id=workspace.id,
        role=WorkspaceRoleEnum.EDIT_ONLY,
        status=InvitationStatusEnum.PENDING.value,
        is_deleted=False,
    )
    db_session.add(link)
    await db_session.commit()

    data = UserCreate(email=email, password="pw", first_name="Un", last_name="Verified")
    await auth_service.onboard(data)

    mock_email_provider.send_email.assert_called_once()


async def test_onboard_exception_user_not_found(db_session: AsyncSession):
    auth_service = AuthService(db_session)
    data = UserCreate(email="ghost@test.com", password="pw", first_name="Ghost", last_name="User")

    with pytest.raises(InvitationNotFoundExceptionError):
        await auth_service.onboard(data)


async def test_onboard_exception_workspace_link_not_found(db_session: AsyncSession):
    auth_service = AuthService(db_session)
    user = User(email="nolink@test.com", first_name=None)
    db_session.add(user)
    await db_session.commit()

    data = UserCreate(email="nolink@test.com", password="pw", first_name="No", last_name="Link")

    with pytest.raises(InvitationNotFoundExceptionError):
        await auth_service.onboard(data)


async def test_onboard_exception_already_onboarded(db_session: AsyncSession):
    auth_service = AuthService(db_session)
    user = User(email="active@test.com", hashed_password="existing_hash", is_whitelisted=True)
    workspace = Workspace(name="Active WS", email="activews@test.com")
    db_session.add_all([user, workspace])
    await db_session.flush()

    link = WorkspaceUser(
        user_id=user.id,
        workspace_id=workspace.id,
        status=InvitationStatusEnum.ACTIVE.value,
        is_deleted=False,
    )
    db_session.add(link)
    await db_session.commit()

    data = UserCreate(email="active@test.com", password="pw", first_name="A", last_name="B")

    with pytest.raises(AccountAlreadyOnboardedExceptionError):
        await auth_service.onboard(data)


async def test_onboard_exception_database_failure_triggers_rollback(db_session: AsyncSession):
    auth_service = AuthService(db_session)

    user = User(email="fail@test.com", first_name=None, hashed_password=None, is_whitelisted=True)
    workspace = Workspace(name="Fail WS", email="faledws@test.com")
    db_session.add_all([user, workspace])
    await db_session.flush()

    link = WorkspaceUser(
        user_id=user.id,
        workspace_id=workspace.id,
        status=InvitationStatusEnum.PENDING.value,
        is_deleted=False,
    )
    db_session.add(link)
    await db_session.commit()

    data = UserCreate(email="fail@test.com", password="pw", first_name="Should", last_name="Fail")

    with (
        patch("erp.api.auth.service.generate_token_pair", side_effect=Exception("Crypto Error")),
        pytest.raises(OnboardingFailedExceptionError),
    ):
        await auth_service.onboard(data)

    # Verify Rollback
    db_session.expire_all()
    await db_session.refresh(user)
    await db_session.refresh(link)

    assert user.first_name is None
    assert user.hashed_password is None
    assert link.status == InvitationStatusEnum.PENDING.value
