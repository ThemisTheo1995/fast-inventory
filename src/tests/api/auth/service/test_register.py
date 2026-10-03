import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.auth.exceptions import (
    OnboardingFailedExceptionError,
    PricingPlanDoesNotExistError,
    UserExistsExceptionError,
)
from erp.api.auth.models import User, UserSession
from erp.api.auth.schemas.user import RegisterRequest, UserCreate
from erp.api.auth.service import AuthService
from erp.api.pricing.enums import PlanName
from erp.api.pricing.models import PricingPlan
from erp.api.workspace.exceptions import WorkspaceAlreadyExistsError
from erp.api.workspace.models import Workspace
from erp.api.workspace.schemas import WorkspaceCreate
from erp.api.workspace_user.enums import InvitationStatusEnum, WorkspaceRoleEnum
from erp.api.workspace_user.models import WorkspaceUser


@patch("erp.api.auth.service.get_email_provider")
async def test_register_happy_path(mock_get_email, db_session: AsyncSession):
    mock_email_provider = AsyncMock()
    mock_get_email.return_value = mock_email_provider
    auth_service = AuthService(db_session)

    request_data = RegisterRequest(
        user=UserCreate(email="happy@example.com", password="SecurePassword123!", first_name="John", last_name="Doe"),
        workspace=WorkspaceCreate(name="Happy Tech LLC", email="billing@happytech.com"),
        plan=next(iter(PlanName)),
    )

    result = await auth_service.register(request_data)

    # Check side effects
    mock_email_provider.send_email.assert_called_once()
    assert result.is_whitelisted is False

    res_ws_user = await db_session.execute(select(WorkspaceUser).join(User).where(User.email == "happy@example.com"))
    workspace_user = res_ws_user.scalar_one_or_none()

    # Check returned DTO and link state (RESTORED ORIGINAL ASSERTIONS)
    assert workspace_user is not None
    assert workspace_user.role == WorkspaceRoleEnum.FULL_ADMIN
    assert workspace_user.status == InvitationStatusEnum.ACTIVE

    # Check Database Mutations (RESTORED ORIGINAL ASSERTIONS)
    res_user = await db_session.execute(select(User).where(User.email == "happy@example.com"))
    user = res_user.scalar_one_or_none()
    assert user is not None
    assert user.first_name == "John"

    res_ws = await db_session.execute(select(Workspace).where(Workspace.name == "Happy Tech LLC"))
    workspace = res_ws.scalar_one_or_none()
    assert workspace is not None
    assert workspace.email == "billing@happytech.com"

    res_session = await db_session.execute(select(UserSession).where(UserSession.user_id == user.id))
    session = res_session.scalar_one_or_none()
    assert session is not None
    assert session.expires_at > datetime.now(UTC)


async def test_register_exception_user_already_exists(db_session: AsyncSession, pricing_plan: PricingPlan):
    auth_service = AuthService(db_session)

    # Setup pre-existing state
    existing_user = User(email="exists@example.com", first_name="Im", last_name="Here", hashed_password="hashed")
    db_session.add(existing_user)
    await db_session.commit()

    request_data = RegisterRequest(
        user=UserCreate(email="exists@example.com", password="password123"),
        workspace=WorkspaceCreate(name="Ghost Corp", email="ghost@corp.com"),
        plan=pricing_plan.name,
    )

    with pytest.raises(UserExistsExceptionError):
        await auth_service.register(request_data)


async def test_register_exception_workspace_already_exists(db_session: AsyncSession):
    auth_service = AuthService(db_session)

    await db_session.execute(delete(PricingPlan))
    plan = PricingPlan(name=PlanName.PRO, listings_limit=10000, api_limit=10000, price_monthly=4800)
    db_session.add(plan)

    taken_email = f"taken_{uuid.uuid4().hex}@corp.com"
    workspace = Workspace(name="Existing", email=taken_email)
    db_session.add(workspace)
    await db_session.commit()

    request_data = RegisterRequest(
        user=UserCreate(
            email=f"new_{uuid.uuid4().hex}@example.com", password="password123", first_name="N", last_name="U"
        ),
        workspace=WorkspaceCreate(name="Whatever", email=taken_email),
        plan=PlanName.PRO,
    )

    with pytest.raises(WorkspaceAlreadyExistsError):
        await auth_service.register(request_data)


async def test_register_exception_database_failure_triggers_rollback(db_session: AsyncSession):
    auth_service = AuthService(db_session)
    request_data = RegisterRequest(
        user=UserCreate(email="rollback@example.com", password="password123"),
        workspace=WorkspaceCreate(name="Rollback Inc", email="rb@inc.com"),
        plan=next(iter(PlanName)),
    )

    # Force an internal failure mid-flight
    with (
        patch("erp.api.auth.service.generate_token_pair", side_effect=ValueError("JWT Crypto System Error")),
        pytest.raises(OnboardingFailedExceptionError),
    ):
        await auth_service.register(request_data)

    # Assert that rollback successfully kept database clean of partial/orphaned items (RESTORED ORIGINAL ASSERTIONS)
    db_session.expire_all()

    res_user = await db_session.execute(select(User).where(User.email == "rollback@example.com"))
    assert res_user.scalar_one_or_none() is None

    res_ws = await db_session.execute(select(Workspace).where(Workspace.name == "Rollback Inc"))
    assert res_ws.scalar_one_or_none() is None


async def test_register_exception_pricing_plan_does_not_exist(db_session: AsyncSession):
    await db_session.execute(delete(PricingPlan))
    await db_session.commit()

    auth_service = AuthService(db_session)
    request_data = RegisterRequest(
        user=UserCreate(email="noplan@example.com", password="SecurePassword123!"),
        workspace=WorkspaceCreate(name="No Plan LLC", email="noplan@corp.com"),
        plan=PlanName.PRO,
    )

    with pytest.raises(PricingPlanDoesNotExistError):
        await auth_service.register(request_data)
