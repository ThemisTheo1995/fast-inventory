import uuid

import pytest

from erp.api.modules.purchase_order.exceptions import (
    PurchaseOrderNotFoundError,
)
from erp.api.modules.purchase_order.service import PurchaseOrderService


@pytest.mark.asyncio
async def test_get_purchase_order_not_found(db_session, seed_workspace, event_bus):
    service = PurchaseOrderService(db_session, event_bus)
    with pytest.raises(PurchaseOrderNotFoundError):
        await service.get_purchase_order(seed_workspace, uuid.uuid4())


@pytest.mark.asyncio
async def test_get_purchase_order_tenant_isolation(db_session, alt_workspace, active_purchase_order, event_bus):
    service = PurchaseOrderService(db_session, event_bus)
    with pytest.raises(PurchaseOrderNotFoundError):
        await service.get_purchase_order(alt_workspace, active_purchase_order.id)
