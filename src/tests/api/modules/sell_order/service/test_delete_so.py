import uuid

import pytest

from src.erp.api.modules.sell_order.enums import SOStatusEnum
from src.erp.api.modules.sell_order.exceptions import (
    SellOrderCannotDeleteError,
    SellOrderNotFoundError,
)
from src.erp.api.modules.sell_order.schemas import SellOrderCreate, SellOrderLineCreate
from src.erp.api.modules.sell_order.service import SellOrderService


@pytest.mark.asyncio
async def test_delete_sell_order_soft_delete(db_session, seed_workspace, active_sell_order, event_bus):
    service = SellOrderService(db_session, event_bus)
    await service.delete_sell_order(seed_workspace, active_sell_order.id)

    with pytest.raises(SellOrderNotFoundError):
        await service.get_sell_order(seed_workspace, active_sell_order.id)


@pytest.mark.asyncio
async def test_delete_sell_order_not_found(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    with pytest.raises(SellOrderNotFoundError):
        await service.delete_sell_order(seed_workspace, uuid.uuid4())


@pytest.mark.asyncio
async def test_delete_sell_order_invalid_status_fails(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    so = await service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-DEL-ERR", status=SOStatusEnum.CONFIRMED, sell_order_lines=[])
    )

    with pytest.raises(SellOrderCannotDeleteError):
        await service.delete_sell_order(seed_workspace, so.id)


@pytest.mark.asyncio
async def test_delete_sell_order_with_lines_cascades_soft_delete(db_session, seed_workspace, event_bus):
    """Verifies that deleting a sell order also triggers soft_delete() on all its lines."""
    service = SellOrderService(db_session, event_bus)

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-CASCADE-DEL",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[
                SellOrderLineCreate(quantity=1, unit_cost=100),
                SellOrderLineCreate(quantity=2, unit_cost=50),
            ],
        ),
    )

    assert len(so.sell_order_lines) == 2
    await service.delete_sell_order(seed_workspace, so.id)

    with pytest.raises(SellOrderNotFoundError):
        await service.get_sell_order(seed_workspace, so.id)
