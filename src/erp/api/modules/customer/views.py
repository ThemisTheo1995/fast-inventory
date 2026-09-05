from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.erp.api.modules.customer.events import (
    CustomerCreatedEvent,
    CustomerUpdatedEvent,
)
from src.erp.api.modules.customer.schemas import (
    CustomerCreate,
    CustomerPaginatedResponse,
    CustomerResponse,
    CustomerUpdate,
)
from src.erp.api.modules.customer.service import CustomerService
from src.erp.core.event_bus import global_event_bus
from src.erp.database.base import get_db

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/customers",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_customer(
    workspace_id: UUID,
    data: CustomerCreate,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> CustomerResponse:
    service = CustomerService(db)

    customer = await service.create_customer(
        workspace_id,
        data,
    )

    background_tasks.add_task(
        global_event_bus.publish,
        CustomerCreatedEvent(
            workspace_id=workspace_id,
            customer=customer,
        ),
    )

    return customer


@router.get(
    "/customers",
    response_model=CustomerPaginatedResponse,
)
async def get_customers(
    workspace_id: UUID,
    db: DbSession,
    search: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> CustomerPaginatedResponse:
    service = CustomerService(db)

    return await service.get_customers(
        workspace_id,
        search,
        page,
        limit,
    )


@router.get(
    "/customers/{customer_id}",
    response_model=CustomerResponse,
)
async def get_customer(
    workspace_id: UUID,
    customer_id: UUID,
    db: DbSession,
) -> CustomerResponse:
    service = CustomerService(db)

    return await service.get_customer(
        workspace_id,
        customer_id,
    )


@router.patch(
    "/customers/{customer_id}",
    response_model=CustomerResponse,
)
async def update_customer(
    workspace_id: UUID,
    customer_id: UUID,
    data: CustomerUpdate,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> CustomerResponse:
    service = CustomerService(db)

    customer = await service.update_customer(
        workspace_id,
        customer_id,
        data,
    )

    background_tasks.add_task(
        global_event_bus.publish,
        CustomerUpdatedEvent(
            workspace_id=workspace_id,
            customer=customer,
        ),
    )

    return customer


@router.delete(
    "/customers/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_customer(
    workspace_id: UUID,
    customer_id: UUID,
    db: DbSession,
) -> None:
    service = CustomerService(db)

    await service.delete_customer(
        workspace_id,
        customer_id,
    )
