import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.auth.exceptions import (
    AccountAlreadyOnboardedExceptionError,
    InvitationNotFoundExceptionError,
    OnboardingFailedExceptionError,
)
from erp.api.auth.models import User, UserSession
from erp.api.auth.schemas.user import UserCreate
from erp.api.auth.service import AuthService
from erp.api.auth.utils import decode_token
from erp.api.workspace.models import Workspace
from erp.api.workspace_user.enums import InvitationStatusEnum, WorkspaceRoleEnum
from erp.api.workspace_user.models import WorkspaceUser


def unique_email(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}@test.com"


async def create_invited_user(
    db_session: AsyncSession,
    *,
    is_whitelisted: bool = True,
    hashed_password: str | None = None,
    status: InvitationStatusEnum = InvitationStatusEnum.PENDING,
    is_deleted: bool = False,
) -> tuple[User, Workspace, WorkspaceUser]:
    user = User(
        email=unique_email("invitee"),
        first_name=None,
        last_name=None,
        is_whitelisted=is_whitelisted,
        hashed_password=hashed_password,
    )

    workspace = Workspace(
        name=f"Invite Workspace {uuid.uuid4().hex[:8]}",
        email=unique_email("workspace"),
    )

    db_session.add_all([user, workspace])
    await db_session.flush()

    link = WorkspaceUser(
        user_id=user.id,
        workspace_id=workspace.id,
        role=WorkspaceRoleEnum.EDIT_ONLY,
        status=status,
        is_deleted=is_deleted,
    )

    db_session.add(link)
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(link)

    return user, workspace, link


async def test_onboard_happy_path(db_session: AsyncSession):
    auth_service = AuthService(db_session)

    user, workspace, link = await create_invited_user(
        db_session,
        is_whitelisted=True,
    )

    email_provider = AsyncMock()

    with patch(
        "erp.api.auth.service.get_email_provider",
        return_value=email_provider,
    ):
        data = UserCreate(
            email=user.email,
            password="NewPassword123!",
            first_name="Jane",
            last_name="Doe",
        )

        result = await auth_service.onboard(data)

    assert result.access_token
    assert result.refresh_token
    assert result.workspace_id == workspace.id
    assert result.is_whitelisted is True
    assert result.whitelisted_token is None

    await db_session.refresh(user)
    await db_session.refresh(link)

    assert user.first_name == "Jane"
    assert user.last_name == "Doe"
    assert user.hashed_password is not None
    assert user.hashed_password != "NewPassword123!"
    assert link.status == InvitationStatusEnum.ACTIVE

    # Whitelisted users do not receive a verification email.
    email_provider.send_email.assert_not_called()

    # Onboarding creates a refresh-token-backed session.
    refresh_payload = decode_token(result.refresh_token)

    session_result = await db_session.execute(select(UserSession).where(UserSession.user_id == user.id))
    session = session_result.scalar_one()

    assert session.session_id == refresh_payload["jti"]


async def test_onboard_unwhitelisted_user_sends_verification_email(
    db_session: AsyncSession,
):
    auth_service = AuthService(db_session)

    user, workspace, link = await create_invited_user(
        db_session,
        is_whitelisted=False,
    )

    email_provider = AsyncMock()

    with patch(
        "erp.api.auth.service.get_email_provider",
        return_value=email_provider,
    ):
        data = UserCreate(
            email=user.email,
            password="NewPassword123!",
            first_name="Un",
            last_name="Verified",
        )

        result = await auth_service.onboard(data)

    assert result.workspace_id == workspace.id
    assert result.is_whitelisted is False

    email_provider.send_email.assert_awaited_once()

    sent_message = email_provider.send_email.await_args.args[0]

    assert user.email in sent_message.recipients
    assert sent_message.subject

    await db_session.refresh(link)
    assert link.status == InvitationStatusEnum.ACTIVE


async def test_onboard_user_not_found(db_session: AsyncSession):
    auth_service = AuthService(db_session)

    data = UserCreate(
        email=unique_email("ghost"),
        password="NewPassword123!",
        first_name="Ghost",
        last_name="User",
    )

    with pytest.raises(InvitationNotFoundExceptionError):
        await auth_service.onboard(data)


async def test_onboard_user_without_invitation_raises_not_found(
    db_session: AsyncSession,
):
    auth_service = AuthService(db_session)

    user = User(
        email=unique_email("nolink"),
        first_name=None,
        hashed_password=None,
        is_whitelisted=True,
    )

    db_session.add(user)
    await db_session.commit()

    data = UserCreate(
        email=user.email,
        password="NewPassword123!",
        first_name="No",
        last_name="Link",
    )

    with pytest.raises(InvitationNotFoundExceptionError):
        await auth_service.onboard(data)


async def test_onboard_already_onboarded_user_raises_error(
    db_session: AsyncSession,
):
    auth_service = AuthService(db_session)

    user, _, _ = await create_invited_user(
        db_session,
        hashed_password="existing_hash",
        status=InvitationStatusEnum.ACTIVE,
    )

    data = UserCreate(
        email=user.email,
        password="NewPassword123!",
        first_name="Already",
        last_name="Onboarded",
    )

    with pytest.raises(AccountAlreadyOnboardedExceptionError):
        await auth_service.onboard(data)


async def test_onboard_soft_deleted_invitation_raises_not_found(
    db_session: AsyncSession,
):
    auth_service = AuthService(db_session)

    user, _, _ = await create_invited_user(
        db_session,
        is_deleted=True,
    )

    data = UserCreate(
        email=user.email,
        password="NewPassword123!",
        first_name="Deleted",
        last_name="Invitation",
    )

    with pytest.raises(InvitationNotFoundExceptionError):
        await auth_service.onboard(data)


async def test_onboard_database_failure_rolls_back_changes(
    db_session: AsyncSession,
):
    auth_service = AuthService(db_session)

    user, _, link = await create_invited_user(
        db_session,
        is_whitelisted=True,
    )

    data = UserCreate(
        email=user.email,
        password="NewPassword123!",
        first_name="Should",
        last_name="Fail",
    )

    with (
        patch(
            "erp.api.auth.service.generate_token_pair",
            side_effect=Exception("Crypto Error"),
        ),
        pytest.raises(OnboardingFailedExceptionError),
    ):
        await auth_service.onboard(data)

    await db_session.refresh(user)
    await db_session.refresh(link)

    assert user.first_name is None
    assert user.last_name is None
    assert user.hashed_password is None
    assert link.status == InvitationStatusEnum.PENDING

    session_result = await db_session.execute(select(UserSession).where(UserSession.user_id == user.id))
    assert session_result.scalar_one_or_none() is None
