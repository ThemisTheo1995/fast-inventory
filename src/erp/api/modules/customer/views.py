from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.erp.api.modules.customer.schemas import (
    CustomerCreate,
    CustomerPaginatedResponse,
    CustomerResponse,
    CustomerUpdate,
)
from src.erp.api.modules.customer.service import CustomerService
from src.erp.database.base import get_db

router = APIRouter()


@router.post("/customers", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    workspace_id: UUID,
    data: CustomerCreate,
    db: Annotated[Session, Depends(get_db)],
) -> CustomerResponse:

    service = CustomerService(db)
    return service.create_customer(workspace_id, data)


@router.get("/customers", response_model=CustomerPaginatedResponse)
def get_customers(
    workspace_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    search: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> CustomerPaginatedResponse:

    service = CustomerService(db)

    return service.get_customers(workspace_id, search, page, limit)


@router.get("/customers/{customer_id}", response_model=CustomerResponse)
def get_customer(
    workspace_id: UUID,
    customer_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> CustomerResponse:

    service = CustomerService(db)
    return service.get_customer(workspace_id, customer_id)


@router.patch("/customers/{customer_id}", response_model=CustomerResponse)
def update_customer(
    workspace_id: UUID,
    customer_id: UUID,
    data: CustomerUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> CustomerResponse:

    service = CustomerService(db)
    return service.update_customer(workspace_id, customer_id, data)


@router.delete("/customers/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    workspace_id: UUID,
    customer_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> None:

    service = CustomerService(db)
    service.delete_customer(workspace_id, customer_id)
