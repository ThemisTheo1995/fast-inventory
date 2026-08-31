from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

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
def create_sell_order(
    workspace_id: UUID,
    data: SellOrderCreate,
    db: Annotated[Session, Depends(get_db)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
) -> SellOrderResponse:

    service = SellOrderService(db, event_bus)
    return service.create_sell_order(workspace_id, data)


@router.get("/sell-orders", response_model=SellOrderPaginatedResponse)
def get_sell_orders(
    workspace_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
    search: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> SellOrderPaginatedResponse:

    service = SellOrderService(db, event_bus)
    return service.get_sell_orders(workspace_id, search, page, limit)


@router.get("/sell-orders/{sell_order_id}", response_model=SellOrderResponse)
def get_sell_order(
    workspace_id: UUID,
    sell_order_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
) -> SellOrderResponse:

    service = SellOrderService(db, event_bus)
    return service.get_sell_order(workspace_id, sell_order_id)


@router.patch("/sell-orders/{sell_order_id}", response_model=SellOrderResponse)
def update_sell_order(
    workspace_id: UUID,
    sell_order_id: UUID,
    data: SellOrderUpdate,
    db: Annotated[Session, Depends(get_db)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
) -> SellOrderResponse:

    service = SellOrderService(db, event_bus)
    return service.update_sell_order(workspace_id, sell_order_id, data)


@router.delete("/sell-orders/{sell_order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sell_order(
    workspace_id: UUID,
    sell_order_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
) -> None:

    service = SellOrderService(db, event_bus)
    service.delete_sell_order(workspace_id, sell_order_id)


# =======================================================
# Sell Order Lines
# =======================================================


@router.post(
    "/sell-orders/{sell_order_id}/lines",
    response_model=SellOrderLineResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_sell_order_line(
    workspace_id: UUID,
    sell_order_id: UUID,
    data: SellOrderLineCreate,
    db: Annotated[Session, Depends(get_db)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
) -> SellOrderLineResponse:

    service = SellOrderService(db, event_bus)
    return service.add_line(workspace_id, sell_order_id, data)


@router.patch("/sell-orders/{sell_order_id}/lines/{line_id}", response_model=SellOrderLineResponse)
def update_sell_order_line(
    workspace_id: UUID,
    sell_order_id: UUID,
    line_id: UUID,
    data: SellOrderLineUpdate,
    db: Annotated[Session, Depends(get_db)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
) -> SellOrderLineResponse:

    service = SellOrderService(db, event_bus)
    return service.update_line(workspace_id, sell_order_id, line_id, data)


@router.delete("/sell-orders/{sell_order_id}/lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_sell_order_line(
    workspace_id: UUID,
    sell_order_id: UUID,
    line_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
) -> None:

    service = SellOrderService(db, event_bus)
    service.remove_line(workspace_id, sell_order_id, line_id)
