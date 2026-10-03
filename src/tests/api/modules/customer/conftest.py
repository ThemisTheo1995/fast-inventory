import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.modules.customer.models import Customer


@pytest.fixture
async def active_customer(
    db_session: AsyncSession,
    seed_workspace,
) -> Customer:
    """Seeds a live customer record attached to the primary workspace."""

    customer = Customer(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        first_name="Active",
        last_name="Customer",
        email="active.customer@test.com",
        is_deleted=False,
    )

    db_session.add(customer)

    await db_session.commit()
    await db_session.refresh(customer)

    return customer


@pytest.fixture(autouse=True)
def silence_event_bus(monkeypatch):
    """
    Prevents router tests from triggering background tasks that spawn
    independent database sessions, keeping our SAVEPOINT transactions safe.
    """
    from erp.core.event_bus import global_event_bus

    mock_publish = AsyncMock()
    monkeypatch.setattr(global_event_bus, "publish", mock_publish)
    return mock_publish
