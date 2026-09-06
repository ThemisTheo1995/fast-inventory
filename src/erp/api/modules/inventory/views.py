from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.modules.inventory.schemas.inventory import (
    InventoryPaginatedResponse,
    InventoryResponse,
)
from erp.api.modules.inventory.schemas.stock_movement import (
    StockMovementCreate,
    StockMovementPaginatedResponse,
    StockMovementResponse,
)
from erp.api.modules.inventory.service import InventoryService
from erp.database.base import get_db

router = APIRouter()

Page = Annotated[int, Query(ge=1)]
Limit = Annotated[int, Query(ge=1, le=100)]
Expand = Annotated[list[str] | None, Query()]


@router.get("/inventory", response_model=InventoryPaginatedResponse)
async def get_inventories(
    workspace_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Page = 1,
    limit: Limit = 20,
    expand: Expand = None,
) -> InventoryPaginatedResponse:

    service = InventoryService(db)

    return await service.get_inventories(workspace_id, page, limit, expand=expand)


@router.get("/inventory/items/{item_id}", response_model=InventoryResponse)
async def get_inventory_by_item(
    workspace_id: UUID,
    item_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InventoryResponse:

    service = InventoryService(db)

    return await service.get_inventory_by_item(workspace_id, item_id)


# --- Stock Movement Endpoints ---


@router.post("/inventory/movements", response_model=StockMovementResponse, status_code=status.HTTP_201_CREATED)
async def create_stock_movement(
    workspace_id: UUID,
    data: StockMovementCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StockMovementResponse:

    service = InventoryService(db)

    return await service.create_stock_movement(workspace_id, data)


@router.get("/inventory/movements", response_model=StockMovementPaginatedResponse)
async def get_stock_movements(
    workspace_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    item_id: UUID | None = None,
    page: Page = 1,
    limit: Limit = 20,
) -> StockMovementPaginatedResponse:

    service = InventoryService(db)

    return await service.get_stock_movements(workspace_id, item_id, page, limit)
