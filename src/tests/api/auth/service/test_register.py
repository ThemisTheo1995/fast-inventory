import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.auth.exceptions import (
    OnboardingFailedExceptionError,
    PricingPlanDoesNotExistError,
    UserExistsExceptionError,
)
from erp.api.auth.models import User, UserSession
from erp.api.auth.schemas.user import RegisterRequest, UserCreate
from erp.api.auth.service import AuthService
from erp.api.auth.utils import decode_token
from erp.api.pricing.enums import PlanName
from erp.api.pricing.models import PricingPlan, PricingSubscription
from erp.api.workspace.exceptions import WorkspaceAlreadyExistsError
from erp.api.workspace.models import Workspace
from erp.api.workspace.schemas import WorkspaceCreate
from erp.api.workspace_user.enums import InvitationStatusEnum, WorkspaceRoleEnum
from erp.api.workspace_user.models import WorkspaceUser


def unique_email(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}@example.com"


def build_register_request(
    *,
    user_email: str | None = None,
    workspace_name: str | None = None,
    workspace_email: str | None = None,
    plan: PlanName | None = None,
) -> RegisterRequest:
    return RegisterRequest(
        user=UserCreate(
            email=user_email or unique_email("register"),
            password="SecurePassword123!",
            first_name="John",
            last_name="Doe",
        ),
        workspace=WorkspaceCreate(
            name=workspace_name or f"Workspace {uuid.uuid4().hex[:8]}",
            email=workspace_email or unique_email("workspace"),
        ),
        plan=plan or next(iter(PlanName)),
    )


async def test_register_happy_path(
    db_session: AsyncSession,
    pricing_plan: PricingPlan,
):
    auth_service = AuthService(db_session)
    email_provider = AsyncMock()
    email_message = object()

    request_data = build_register_request(plan=pricing_plan.name)

    with (
        patch(
            "erp.api.auth.service.get_email_provider",
            return_value=email_provider,
        ),
        patch(
            "erp.api.auth.service.build_welcome_email",
            return_value=email_message,
        ) as build_email,
    ):
        result = await auth_service.register(request_data)

    email_provider.send_email.assert_awaited_once_with(email_message)

    build_email.assert_called_once()
    assert build_email.call_args.kwargs["recipient"] == request_data.user.email
    assert build_email.call_args.kwargs["whitelisted_token"] == result.whitelisted_token

    assert result.access_token
    assert result.refresh_token
    assert result.whitelisted_token
    assert result.is_whitelisted is False

    access_payload = decode_token(result.access_token)
    refresh_payload = decode_token(result.refresh_token)

    assert access_payload["sub"]
    assert refresh_payload["sub"] == access_payload["sub"]
    assert refresh_payload["type"] == "refresh"

    user_result = await db_session.execute(select(User).where(User.email == request_data.user.email))
    user = user_result.scalar_one()

    assert user.first_name == "John"
    assert user.last_name == "Doe"
    assert user.hashed_password is not None
    assert user.is_whitelisted is False

    workspace_result = await db_session.execute(
        select(Workspace).where(Workspace.email == request_data.workspace.email)
    )
    workspace = workspace_result.scalar_one()

    assert workspace.name == request_data.workspace.name
    assert result.workspace_id == workspace.id

    membership_result = await db_session.execute(
        select(WorkspaceUser).where(
            WorkspaceUser.user_id == user.id,
            WorkspaceUser.workspace_id == workspace.id,
        )
    )
    membership = membership_result.scalar_one()

    assert membership.role == WorkspaceRoleEnum.FULL_ADMIN
    assert membership.status == InvitationStatusEnum.ACTIVE

    subscription_result = await db_session.execute(
        select(PricingSubscription).where(PricingSubscription.workspace_id == workspace.id)
    )
    subscription = subscription_result.scalar_one()

    assert subscription.plan_id == pricing_plan.id
    assert subscription.is_active is True
    assert subscription.is_paused is False

    session_result = await db_session.execute(select(UserSession).where(UserSession.user_id == user.id))
    session = session_result.scalar_one()

    assert session.session_id == refresh_payload["jti"]
    assert session.expires_at == datetime.fromtimestamp(
        refresh_payload["exp"],
        tz=UTC,
    )


async def test_register_user_already_exists(
    db_session: AsyncSession,
    pricing_plan: PricingPlan,
):
    auth_service = AuthService(db_session)

    email = unique_email("existing")
    existing_user = User(
        email=email,
        first_name="Existing",
        last_name="User",
        hashed_password="hashed",
    )
    db_session.add(existing_user)
    await db_session.commit()

    request_data = build_register_request(
        user_email=email,
        plan=pricing_plan.name,
    )

    with pytest.raises(UserExistsExceptionError):
        await auth_service.register(request_data)


async def test_register_workspace_already_exists(
    db_session: AsyncSession,
    pricing_plan: PricingPlan,
):
    auth_service = AuthService(db_session)

    taken_email = unique_email("taken")
    workspace = Workspace(
        name="Existing Workspace",
        email=taken_email,
    )
    db_session.add(workspace)
    await db_session.commit()

    request_data = build_register_request(
        workspace_email=taken_email,
        plan=pricing_plan.name,
    )

    with pytest.raises(WorkspaceAlreadyExistsError):
        await auth_service.register(request_data)

    # User creation must not happen when workspace validation fails.
    user_result = await db_session.execute(select(User).where(User.email == request_data.user.email))
    assert user_result.scalar_one_or_none() is None


async def test_register_pricing_plan_does_not_exist():
    """Registration fails when the requested pricing plan cannot be found."""
    db_session = AsyncMock(spec=AsyncSession)

    empty_result = MagicMock()
    empty_result.scalar_one_or_none.return_value = None

    db_session.execute.side_effect = [
        empty_result,
        empty_result,
    ]

    auth_service = AuthService(db_session)
    request_data = build_register_request(plan=PlanName.PRO)

    with pytest.raises(PricingPlanDoesNotExistError):
        await auth_service.register(request_data)

    assert db_session.execute.await_count == 2
    db_session.add.assert_not_called()
    db_session.commit.assert_not_awaited()


async def test_register_database_failure_rolls_back(
    db_session: AsyncSession,
    pricing_plan: PricingPlan,
):
    auth_service = AuthService(db_session)

    request_data = build_register_request(
        plan=pricing_plan.name,
    )

    with (
        patch(
            "erp.api.auth.service.generate_token_pair",
            side_effect=ValueError("JWT Crypto System Error"),
        ),
        pytest.raises(OnboardingFailedExceptionError),
    ):
        await auth_service.register(request_data)

    user_result = await db_session.execute(select(User).where(User.email == request_data.user.email))
    assert user_result.scalar_one_or_none() is None

    workspace_result = await db_session.execute(
        select(Workspace).where(Workspace.email == request_data.workspace.email)
    )
    assert workspace_result.scalar_one_or_none() is None


async def test_register_email_failure_keeps_committed_registration(
    db_session: AsyncSession,
    pricing_plan: PricingPlan,
):
    auth_service = AuthService(db_session)

    email_provider = AsyncMock()
    email_provider.send_email.side_effect = RuntimeError("Email delivery failed")

    request_data = build_register_request(plan=pricing_plan.name)

    with (
        patch(
            "erp.api.auth.service.get_email_provider",
            return_value=email_provider,
        ),
        patch(
            "erp.api.auth.service.build_welcome_email",
            return_value=object(),
        ),
        pytest.raises(RuntimeError, match="Email delivery failed"),
    ):
        await auth_service.register(request_data)

    # Registration was committed before email delivery was attempted.
    user_result = await db_session.execute(select(User).where(User.email == request_data.user.email))
    user = user_result.scalar_one()

    assert user.is_whitelisted is False

    workspace_result = await db_session.execute(
        select(Workspace).where(Workspace.email == request_data.workspace.email)
    )
    workspace = workspace_result.scalar_one()

    assert workspace.name == request_data.workspace.name

    membership_result = await db_session.execute(
        select(WorkspaceUser).where(
            WorkspaceUser.user_id == user.id,
            WorkspaceUser.workspace_id == workspace.id,
        )
    )
    assert membership_result.scalar_one_or_none() is not None

    session_result = await db_session.execute(select(UserSession).where(UserSession.user_id == user.id))
    assert session_result.scalar_one_or_none() is not None
