import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.auth.models import User
from erp.api.auth.utils import create_access_token
from erp.api.pricing.enums import PlanName
from erp.api.pricing.models import PricingPlan, PricingSubscription
from erp.api.workspace.models import Workspace
from erp.api.workspace_user.enums import InvitationStatusEnum, WorkspaceRoleEnum
from erp.api.workspace_user.models import WorkspaceUser
from erp.database.base import get_db
from erp.main import app

# --- WORKSPACE FIXTURES ---


@pytest_asyncio.fixture
async def seed_workspace(db_session: AsyncSession) -> uuid.UUID:
    """Seeds a live primary workspace row with status safety flags."""
    ws_id = uuid.uuid4()
    workspace = Workspace(id=ws_id, name="Primary Test Workspace", email=f"primary-{ws_id}@test.com", is_deleted=False)
    db_session.add(workspace)
    await db_session.commit()
    return ws_id


@pytest_asyncio.fixture
async def alt_workspace(db_session: AsyncSession) -> uuid.UUID:
    """Seeds an alternate workspace row for isolation tracking tests."""
    ws_id = uuid.uuid4()
    workspace = Workspace(id=ws_id, name="Alternative Test Workspace", email=f"alt-{ws_id}@test.com", is_deleted=False)
    db_session.add(workspace)
    await db_session.commit()
    return ws_id


# --- PRICING & SUBSCRIPTION FIXTURES ---


@pytest_asyncio.fixture
async def pricing_plan(db_session: AsyncSession) -> PricingPlan:
    """Seeds a real default pricing plan required by subscriptions."""
    plan = PricingPlan(id=uuid.uuid4(), name=next(iter(PlanName)), listings_limit=100, api_limit=1000, price_monthly=0)
    db_session.add(plan)
    await db_session.commit()
    return plan


@pytest_asyncio.fixture
async def active_subscription(
    db_session: AsyncSession, seed_workspace: uuid.UUID, pricing_plan: PricingPlan
) -> PricingSubscription:
    """Fulfills middleware tier-validation with active timestamps."""
    subscription = PricingSubscription(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        plan_id=pricing_plan.id,
        is_active=True,
    )
    db_session.add(subscription)
    await db_session.commit()
    return subscription


# --- AUTHENTICATION & USER FIXTURES ---


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Seeds a fully verified active user account using native UUID formatting."""
    user = User(
        id=uuid.uuid4(), email="test-integrations@company.com", first_name="Test", last_name="User", is_deleted=False
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def active_workspace_user(db_session: AsyncSession, seed_workspace: uuid.UUID, test_user: User) -> WorkspaceUser:
    """Binds the user to the workspace with maximum administrative authorization."""
    ws_user = WorkspaceUser(
        id=uuid.uuid4(),
        user_id=test_user.id,
        workspace_id=seed_workspace,
        status=InvitationStatusEnum.ACTIVE,
        is_deleted=False,
        role=WorkspaceRoleEnum.FULL_ADMIN,
    )
    db_session.add(ws_user)
    await db_session.commit()
    return ws_user


@pytest.fixture
def access_token(test_user: User) -> str:
    """Standard sync fixture because token generation doesn't require DB access."""
    return create_access_token(subject=str(test_user.id))


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    active_workspace_user: WorkspaceUser,  # noqa
    active_subscription: PricingSubscription,  # noqa
    access_token: str,
) -> AsyncGenerator[AsyncClient]:
    """Overridden Async HTTP client injecting database state and valid credentials."""

    # 1. Override the database dependency
    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # 2. Setup AsyncClient with cookies injected natively
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"access_token": access_token},
    ) as test_client:
        yield test_client

    # 3. Cleanup overrides after the test finishes
    app.dependency_overrides.clear()
