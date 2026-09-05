from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.erp.api.modules.supplier.schemas import (
    SupplierCreate,
    SupplierPaginatedResponse,
    SupplierResponse,
    SupplierUpdate,
)
from src.erp.api.modules.supplier.service import SupplierService
from src.erp.database.base import get_db

router = APIRouter()


@router.post("/suppliers", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    workspace_id: UUID,
    data: SupplierCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SupplierResponse:

    service = SupplierService(db)

    return await service.create_supplier(workspace_id, data)


@router.get("/suppliers", response_model=SupplierPaginatedResponse)
async def get_suppliers(
    workspace_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> SupplierPaginatedResponse:

    service = SupplierService(db)

    return await service.get_suppliers(workspace_id, search, page, limit)


@router.get("/suppliers/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    workspace_id: UUID,
    supplier_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SupplierResponse:

    service = SupplierService(db)

    return await service.get_supplier(workspace_id, supplier_id)


@router.patch("/suppliers/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    workspace_id: UUID,
    supplier_id: UUID,
    data: SupplierUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SupplierResponse:

    service = SupplierService(db)

    return await service.update_supplier(workspace_id, supplier_id, data)


@router.delete("/suppliers/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(
    workspace_id: UUID,
    supplier_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:

    service = SupplierService(db)

    await service.delete_supplier(workspace_id, supplier_id)
