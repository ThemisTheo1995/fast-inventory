import uuid

import pytest

from erp.api.modules.bin.models import Bin
from erp.api.modules.item.models import Item


@pytest.fixture
async def seed_bin(db_session, seed_workspace):
    bin_obj = Bin(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        code=f"TEST-{uuid.uuid4().hex[:8].upper()}",
        zone="Test Warehouse",
        is_deleted=False,
    )

    db_session.add(bin_obj)
    await db_session.commit()
    await db_session.refresh(bin_obj)

    return bin_obj


@pytest.fixture
async def active_item(db_session, seed_workspace):
    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        sku=f"TEST-{uuid.uuid4().hex[:8].upper()}",
        title="Test Item",
        base_price=100,
        is_deleted=False,
    )

    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)

    return item
