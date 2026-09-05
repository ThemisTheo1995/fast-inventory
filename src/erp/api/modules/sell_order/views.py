from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.erp.api.modules.sell_order.schemas import (
    SellOrderCreate,
    SellOrderLineCreate,
    SellOrderLineResponse,
    SellOrderLineUpdate,
    SellOrderPaginatedResponse,
    SellOrderResponse,
    SellOrderUpdate,
)
from src.erp.api.modules.sell_order.service import SellOrderService
from src.erp.core.dependencies import get_event_bus
from src.erp.core.event_bus import EventBus
from src.erp.database.base import get_db

router = APIRouter()

# =======================================================
# Sell Orders
# =======================================================


@router.post("/sell-orders", response_model=SellOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_sell_order(
    workspace_id: UUID,
    data: SellOrderCreate,
    db: Annotated[AsyncSession, Depends(get_db)]
) -> SellOrderResponse:

    service = SellOrderService(db)

    return await service.create_sell_order(workspace_id, data)


@router.get("/sell-orders", response_model=SellOrderPaginatedResponse)
async def get_sell_orders(
    workspace_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> SellOrderPaginatedResponse:

    service = SellOrderService(db)

    return await service.get_sell_orders(workspace_id, search, page, limit)


@router.get("/sell-orders/{sell_order_id}", response_model=SellOrderResponse)
async def get_sell_order(
    workspace_id: UUID,
    sell_order_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)]
) -> SellOrderResponse:

    service = SellOrderService(db)

    return await service.get_sell_order(workspace_id, sell_order_id)


@router.patch("/sell-orders/{sell_order_id}", response_model=SellOrderResponse)
async def update_sell_order(
    workspace_id: UUID,
    sell_order_id: UUID,
    data: SellOrderUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
) -> SellOrderResponse:

    service = SellOrderService(db, event_bus)
    return await service.update_sell_order(workspace_id, sell_order_id, data)


@router.delete("/sell-orders/{sell_order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sell_order(
    workspace_id: UUID,
    sell_order_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)]
) -> None:

    service = SellOrderService(db)
    await service.delete_sell_order(workspace_id, sell_order_id)


# =======================================================
# Sell Order Lines
# =======================================================


@router.post(
    "/sell-orders/{sell_order_id}/lines",
    response_model=SellOrderLineResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_sell_order_line(
    workspace_id: UUID,
    sell_order_id: UUID,
    data: SellOrderLineCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
) -> SellOrderLineResponse:

    service = SellOrderService(db, event_bus)
    return await service.add_line(workspace_id, sell_order_id, data)


@router.patch("/sell-orders/{sell_order_id}/lines/{line_id}", response_model=SellOrderLineResponse)
async def update_sell_order_line(
    workspace_id: UUID,
    sell_order_id: UUID,
    line_id: UUID,
    data: SellOrderLineUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
) -> SellOrderLineResponse:

    service = SellOrderService(db, event_bus)
    return await service.update_line(workspace_id, sell_order_id, line_id, data)


@router.delete("/sell-orders/{sell_order_id}/lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_sell_order_line(
    workspace_id: UUID,
    sell_order_id: UUID,
    line_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
) -> None:

    service = SellOrderService(db, event_bus)
    await service.remove_line(workspace_id, sell_order_id, line_id)
