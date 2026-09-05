import uuid

import pytest_asyncio

from src.erp.api.modules.item.models import Item


@pytest_asyncio.fixture
async def active_item(db_session, seed_workspace) -> Item:
    """Seeds a live item record attached to the primary workspace."""
    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        title="Active Test Item",
        sku="TEST-SKU-ACTIVE",
        base_price=1000,
        is_deleted=False,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return item
