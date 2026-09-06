from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.modules.item.schemas import ItemCreate, ItemPaginatedResponse, ItemResponse, ItemUpdate
from erp.api.modules.item.service import ItemService
from erp.database.base import get_db

router = APIRouter()


@router.post("/items", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    workspace_id: UUID,
    data: ItemCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ItemResponse:

    service = ItemService(db)
    return await service.create_item(workspace_id, data)


@router.get("/items", response_model=ItemPaginatedResponse)
async def get_items(
    workspace_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> ItemPaginatedResponse:

    service = ItemService(db)

    return await service.get_items(workspace_id, search, page, limit)


@router.get("/items/{item_id}", response_model=ItemResponse)
async def get_item(
    workspace_id: UUID,
    item_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ItemResponse:

    service = ItemService(db)
    return await service.get_item(workspace_id, item_id)


@router.patch("/items/{item_id}", response_model=ItemResponse)
async def update_item(
    workspace_id: UUID,
    item_id: UUID,
    data: ItemUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ItemResponse:

    service = ItemService(db)
    return await service.update_item(workspace_id, item_id, data)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    workspace_id: UUID,
    item_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:

    service = ItemService(db)
    await service.delete_item(workspace_id, item_id)
