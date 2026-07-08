from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

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
def create_supplier(
    workspace_id: UUID,
    data: SupplierCreate,
    db: Annotated[Session, Depends(get_db)],
) -> SupplierResponse:

    service = SupplierService(db)

    return service.create_supplier(workspace_id, data)


@router.get("/suppliers", response_model=SupplierPaginatedResponse)
def get_suppliers(
    workspace_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    search: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> SupplierPaginatedResponse:

    service = SupplierService(db)

    return service.get_suppliers(workspace_id, search, page, limit)


@router.get("/suppliers/{supplier_id}", response_model=SupplierResponse)
def get_supplier(
    workspace_id: UUID,
    supplier_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> SupplierResponse:

    service = SupplierService(db)

    return service.get_supplier(workspace_id, supplier_id)


@router.patch("/suppliers/{supplier_id}", response_model=SupplierResponse)
def update_supplier(
    workspace_id: UUID,
    supplier_id: UUID,
    data: SupplierUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> SupplierResponse:

    service = SupplierService(db)

    return service.update_supplier(workspace_id, supplier_id, data)


@router.delete("/suppliers/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(
    workspace_id: UUID,
    supplier_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> None:

    service = SupplierService(db)

    service.delete_supplier(workspace_id, supplier_id)
