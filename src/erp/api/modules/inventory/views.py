from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from src.erp.api.modules.inventory.schemas import (
    InventoryPaginatedResponse,
    InventoryResponse,
    StockMovementCreate,
    StockMovementPaginatedResponse,
    StockMovementResponse,
)
from src.erp.api.modules.inventory.service import InventoryService
from src.erp.database.base import get_db

router = APIRouter()


@router.get("/inventory", response_model=InventoryPaginatedResponse)
def get_inventories(
    workspace_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> InventoryPaginatedResponse:

    service = InventoryService(db)

    return service.get_inventories(workspace_id, page, limit)


@router.get("/inventory/items/{item_id}", response_model=InventoryResponse)
def get_inventory_by_item(
    workspace_id: UUID,
    item_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> InventoryResponse:

    service = InventoryService(db)

    return service.get_inventory_by_item(workspace_id, item_id)


# --- Stock Movement Endpoints ---


@router.post("/inventory/movements", response_model=StockMovementResponse, status_code=status.HTTP_201_CREATED)
def create_stock_movement(
    workspace_id: UUID,
    data: StockMovementCreate,
    db: Annotated[Session, Depends(get_db)],
) -> StockMovementResponse:

    service = InventoryService(db)

    return service.create_stock_movement(workspace_id, data)


@router.get("/inventory/movements", response_model=StockMovementPaginatedResponse)
def get_stock_movements(
    workspace_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    item_id: UUID | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> StockMovementPaginatedResponse:

    service = InventoryService(db)

    return service.get_stock_movements(workspace_id, item_id, page, limit)
