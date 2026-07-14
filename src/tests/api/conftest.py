import uuid

import pytest
from fastapi.testclient import TestClient

from src.erp.api.auth.models import User
from src.erp.api.auth.utils import create_access_token
from src.erp.api.pricing.enums import PlanName
from src.erp.api.pricing.models import PricingPlan, PricingSubscription
from src.erp.api.workspace.models import Workspace
from src.erp.api.workspace_user.enums import InvitationStatusEnum, WorkspaceRoleEnum
from src.erp.api.workspace_user.models import WorkspaceUser
from src.erp.database.base import get_db
from src.erp.main import app

# --- WORKSPACE FIXTURES ---


@pytest.fixture
def seed_workspace(db_session) -> uuid.UUID:
    """Seeds a live primary workspace row with status safety flags."""
    ws_id = uuid.uuid4()
    workspace = Workspace(id=ws_id, name="Primary Test Workspace", email=f"primary-{ws_id}@test.com", is_deleted=False)
    db_session.add(workspace)
    db_session.commit()
    return ws_id


@pytest.fixture
def alt_workspace(db_session) -> uuid.UUID:
    """Seeds an alternate workspace row for isolation tracking tests."""
    ws_id = uuid.uuid4()
    workspace = Workspace(id=ws_id, name="Alternative Test Workspace", email=f"alt-{ws_id}@test.com", is_deleted=False)
    db_session.add(workspace)
    db_session.commit()
    return ws_id


# --- PRICING & SUBSCRIPTION FIXTURES ---


@pytest.fixture
def pricing_plan(db_session) -> PricingPlan:
    """Seeds a real default pricing plan required by subscriptions."""
    plan = PricingPlan(id=uuid.uuid4(), name=next(iter(PlanName)), listings_limit=100, api_limit=1000, price_monthly=0)
    db_session.add(plan)
    db_session.commit()
    return plan


@pytest.fixture
def active_subscription(db_session, seed_workspace, pricing_plan):
    """Fulfills middleware tier-validation with active timestamps."""
    subscription = PricingSubscription(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        plan_id=pricing_plan.id,
        is_active=True,
    )
    db_session.add(subscription)
    db_session.commit()
    return subscription


# --- AUTHENTICATION & USER FIXTURES ---


@pytest.fixture
def test_user(db_session):
    """Seeds a fully verified active user account using native UUID formatting."""
    user = User(
        id=uuid.uuid4(), email="test-integrations@company.com", first_name="Test", last_name="User", is_deleted=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def active_workspace_user(db_session, seed_workspace, test_user):
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
    db_session.commit()
    return ws_user


@pytest.fixture
def access_token(test_user):
    return create_access_token(subject=str(test_user.id))


@pytest.fixture
def client(db_session, active_workspace_user, active_subscription, access_token):  # noqa
    """Overridden test client injecting database state and valid credentials."""
    app.dependency_overrides[get_db] = lambda: db_session

    with TestClient(app) as test_client:
        test_client.cookies.set("access_token", access_token)
        yield test_client

    app.dependency_overrides.clear()
