import uuid

import pytest

from src.erp.api.modules.supplier.models import Supplier


@pytest.fixture
async def active_supplier(db_session, seed_workspace) -> Supplier:
    """Seeds a live supplier record bound to the primary workspace context."""
    supplier = Supplier(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        name="Global Logistics Inc",
        email="info@globallogistics.com",
        is_deleted=False,
    )

    db_session.add(supplier)
    await db_session.commit()
    await db_session.refresh(supplier)
    return supplier
