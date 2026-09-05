from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.erp.api.modules.purchase_order.filters.purchase_order import PurchaseOrderFilter
from src.erp.api.modules.purchase_order.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
    PurchaseOrderLineResponse,
    PurchaseOrderLineUpdate,
    PurchaseOrderPaginatedResponse,
    PurchaseOrderResponse,
    PurchaseOrderUpdate,
)
from src.erp.api.modules.purchase_order.service import PurchaseOrderService
from src.erp.core.dependencies import get_event_bus
from src.erp.core.event_bus import EventBus
from src.erp.database.base import get_db

router = APIRouter()

# =======================================================
# Purchase Orders
# =======================================================


@router.post("/purchase-orders", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    workspace_id: UUID,
    data: PurchaseOrderCreate,
    db: Annotated[AsyncSession, Depends(get_db)]
) -> PurchaseOrderResponse:

    service = PurchaseOrderService(db)

    return await service.create_purchase_order(workspace_id, data)


@router.get("/purchase-orders", response_model=PurchaseOrderPaginatedResponse)
async def get_purchase_orders(
    workspace_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    filters: Annotated[PurchaseOrderFilter, Depends()],
    search: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> PurchaseOrderPaginatedResponse:

    service = PurchaseOrderService(db)

    return await service.get_purchase_orders(
        workspace_id=workspace_id,
        filters=filters,
        search=search,
        page=page,
        limit=limit,
    )


@router.get("/purchase-orders/{purchase_order_id}", response_model=PurchaseOrderResponse)
async def get_purchase_order(
    workspace_id: UUID,
    purchase_order_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PurchaseOrderResponse:

    service = PurchaseOrderService(db)

    return await service.get_purchase_order(workspace_id, purchase_order_id)


@router.patch("/purchase-orders/{purchase_order_id}", response_model=PurchaseOrderResponse)
async def update_purchase_order(
    workspace_id: UUID,
    purchase_order_id: UUID,
    data: PurchaseOrderUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
) -> PurchaseOrderResponse:

    service = PurchaseOrderService(db, event_bus)

    return await service.update_purchase_order(workspace_id, purchase_order_id, data)


@router.delete("/purchase-orders/{purchase_order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_purchase_order(
    workspace_id: UUID,
    purchase_order_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)]
) -> None:

    service = PurchaseOrderService(db)

    await service.delete_purchase_order(workspace_id, purchase_order_id)


# =======================================================
# Purchase Order Lines (via PurchaseOrderService)
# =======================================================


@router.post(
    "/purchase-orders/{purchase_order_id}/lines",
    response_model=PurchaseOrderLineResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_purchase_order_line(
    workspace_id: UUID,
    purchase_order_id: UUID,
    data: PurchaseOrderLineCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
) -> PurchaseOrderLineResponse:

    service = PurchaseOrderService(db, event_bus)

    return await service.add_line(workspace_id, purchase_order_id, data)


@router.patch("/purchase-orders/{purchase_order_id}/lines/{line_id}", response_model=PurchaseOrderLineResponse)
async def update_purchase_order_line(
    workspace_id: UUID,
    purchase_order_id: UUID,
    line_id: UUID,
    data: PurchaseOrderLineUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
) -> PurchaseOrderLineResponse:

    service = PurchaseOrderService(db, event_bus)

    return await service.update_line(workspace_id, purchase_order_id, line_id, data)


@router.delete("/purchase-orders/{purchase_order_id}/lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_purchase_order_line(
    workspace_id: UUID,
    purchase_order_id: UUID,
    line_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
) -> None:

    service = PurchaseOrderService(db, event_bus)

    await service.remove_line(workspace_id, purchase_order_id, line_id)
