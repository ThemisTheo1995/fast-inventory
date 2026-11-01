from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.modules.bin.events import (
    BinCreatedEvent,
    BinUpdatedEvent,
)
from erp.api.modules.bin.schemas.bin import (
    BinCreate,
    BinPaginatedResponse,
    BinResponse,
    BinUpdate,
)
from erp.api.modules.bin.schemas.bin_expanded import BinExpandedPaginatedResponse, BinExpandedResponse
from erp.api.modules.bin.service import BinService
from erp.core.event_bus import global_event_bus
from erp.database.base import get_db

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]
Page = Annotated[int, Query(ge=1)]
Limit = Annotated[int, Query(ge=1, le=100)]
Expand = Annotated[list[str] | None, Query()]


@router.post("/bins", response_model=BinResponse, status_code=status.HTTP_201_CREATED)
async def create_bin(
    workspace_id: UUID,
    data: BinCreate,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> BinResponse:
    service = BinService(db)

    bin = await service.create_bin(
        workspace_id,
        data,
    )

    background_tasks.add_task(
        global_event_bus.publish,
        BinCreatedEvent(
            workspace_id=workspace_id,
            bin=bin,
        ),
    )

    return bin


@router.get("/bins", response_model=BinPaginatedResponse | BinExpandedPaginatedResponse)
async def get_bins(
    workspace_id: UUID,
    db: DbSession,
    search: str | None = None,
    page: Page = 1,
    limit: Limit = 20,
    expand: Expand = None,
) -> BinPaginatedResponse | BinExpandedPaginatedResponse:
    service = BinService(db)

    return await service.get_bins(workspace_id, search, page, limit, expand)


@router.get("/bins/{bin_id}", response_model=BinResponse | BinExpandedResponse)
async def get_bin(
    workspace_id: UUID,
    bin_id: UUID,
    db: DbSession,
    expand: Expand = None,
) -> BinResponse | BinExpandedResponse:

    service = BinService(db)

    return await service.get_bin(workspace_id, bin_id, expand=expand)


@router.patch("/bins/{bin_id}", response_model=BinResponse)
async def update_bin(
    workspace_id: UUID,
    bin_id: UUID,
    data: BinUpdate,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> BinResponse:
    service = BinService(db)

    bin = await service.update_bin(
        workspace_id,
        bin_id,
        data,
    )

    background_tasks.add_task(
        global_event_bus.publish,
        BinUpdatedEvent(
            workspace_id=workspace_id,
            bin=bin,
        ),
    )

    return bin


@router.delete("/bins/{bin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bin(
    workspace_id: UUID,
    bin_id: UUID,
    db: DbSession,
) -> None:
    service = BinService(db)

    await service.delete_bin(workspace_id, bin_id)
