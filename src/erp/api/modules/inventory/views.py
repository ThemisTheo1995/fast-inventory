from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.modules.inventory.filters.inventory import InventoryFilter
from erp.api.modules.inventory.schemas.inventory import InventoryPaginatedResponse, InventoryResponse, InventoryUpdate
from erp.api.modules.inventory.schemas.inventory_expanded import (
    InventoryExpandedPaginatedResponse,
    InventoryExpandedResponse,
)
from erp.api.modules.inventory.schemas.stock_movement import (
    StockMovementCreate,
    StockMovementPaginatedResponse,
    StockMovementResponse,
)
from erp.api.modules.inventory.schemas.transfer import InventoryTransferRequest
from erp.api.modules.inventory.service import InventoryService, InventoryTransferService
from erp.database.base import get_db

router = APIRouter()

Page = Annotated[int, Query(ge=1)]
Limit = Annotated[int, Query(ge=1, le=100)]
Expand = Annotated[list[str] | None, Query()]


# --- Static / Specific Routes First (Order Matters) ---


@router.post("/inventory/transfer-bin-to-bin", status_code=status.HTTP_200_OK)
async def transfer_inventory_stock(
    workspace_id: UUID,
    payload: InventoryTransferRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """
    Transfer item inventory quantities between bins (bin-to-bin transfer).
    """
    service = InventoryTransferService(db)

    await service.bin_to_bin_transfer(workspace_id=workspace_id, data=payload)
    return {"message": "Stock transferred successfully"}


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
    bin_id: UUID | None = None,
    page: Page = 1,
    limit: Limit = 20,
) -> StockMovementPaginatedResponse:

    service = InventoryService(db)

    return await service.get_stock_movements(workspace_id, item_id, bin_id, page, limit)


@router.get("/inventory/{inventory_id}", response_model=InventoryResponse | InventoryExpandedResponse)
async def get_inventory(
    workspace_id: UUID,
    inventory_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    expand: Expand = None,
) -> InventoryResponse | InventoryExpandedResponse:

    service = InventoryService(db)

    return await service.get_inventory(workspace_id, inventory_id, expand=expand)


@router.get("/inventory", response_model=InventoryPaginatedResponse | InventoryExpandedPaginatedResponse)
async def get_inventories(
    workspace_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    filters: Annotated[InventoryFilter, Depends()],
    search: str | None = None,
    page: int = 1,
    limit: int = 20,
    expand: Expand = None,
) -> InventoryPaginatedResponse | InventoryExpandedPaginatedResponse:

    service = InventoryService(db)

    return await service.get_inventories(
        workspace_id=workspace_id,
        filters=filters,
        search=search,
        page=page,
        limit=limit,
        expand=expand,
    )


@router.patch("/inventory/{inventory_id}", response_model=InventoryResponse, status_code=status.HTTP_200_OK)
async def update_inventory(
    workspace_id: UUID,
    inventory_id: UUID,
    data: InventoryUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InventoryResponse:
    service = InventoryService(db)

    return await service.update_inventory(
        workspace_id=workspace_id,
        inventory_id=inventory_id,
        data=data,
    )


@router.delete(
    "/inventory/{inventory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_inventory(
    workspace_id: UUID,
    inventory_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = InventoryService(db)

    await service.delete_inventory(workspace_id, inventory_id)
