from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.erp.api.modules.item.schemas import ItemCreate, ItemPaginatedResponse, ItemResponse, ItemUpdate
from src.erp.api.modules.item.service import ItemService
from src.erp.database.base import get_db

router = APIRouter()


@router.post("/items", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def create_item(
    workspace_id: UUID,
    data: ItemCreate,
    db: Annotated[Session, Depends(get_db)],
) -> ItemResponse:

    service = ItemService(db)
    return service.create_item(workspace_id, data)


@router.get("/items", response_model=ItemPaginatedResponse)
def get_items(
    workspace_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    search: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> ItemPaginatedResponse:

    service = ItemService(db)

    return service.get_items(workspace_id, search, page, limit)


@router.get("/items/{item_id}", response_model=ItemResponse)
def get_item(
    workspace_id: UUID,
    item_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ItemResponse:

    service = ItemService(db)
    return service.get_item(workspace_id, item_id)


@router.patch("/items/{item_id}", response_model=ItemResponse)
def update_item(
    workspace_id: UUID,
    item_id: UUID,
    data: ItemUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> ItemResponse:

    service = ItemService(db)
    return service.update_item(workspace_id, item_id, data)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    workspace_id: UUID,
    item_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> None:

    service = ItemService(db)
    service.delete_item(workspace_id, item_id)
