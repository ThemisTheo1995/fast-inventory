import uuid

import pytest

from src.erp.api.modules.sell_order.exceptions import SellOrderNotFoundError
from src.erp.api.modules.sell_order.service import SellOrderService


@pytest.mark.asyncio
async def test_get_sell_order_not_found(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    with pytest.raises(SellOrderNotFoundError):
        await service.get_sell_order(seed_workspace, uuid.uuid4())


@pytest.mark.asyncio
async def test_get_sell_order_tenant_isolation(db_session, alt_workspace, active_sell_order, event_bus):
    service = SellOrderService(db_session, event_bus)
    with pytest.raises(SellOrderNotFoundError):
        await service.get_sell_order(alt_workspace, active_sell_order.id)
