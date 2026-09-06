from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.workspace.schemas import (
    WorkspaceResponse,
    WorkspaceUpdate,
)
from erp.api.workspace.service import WorkspaceService
from erp.database.base import get_db

router = APIRouter()


@router.get("", response_model=WorkspaceResponse)
async def get_workspace(workspace_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]) -> WorkspaceResponse:

    service = WorkspaceService(db)
    return await service.get_workspace(workspace_id)


@router.patch("", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: UUID,
    update_data: WorkspaceUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceResponse:

    service = WorkspaceService(db)
    return await service.update_workspace(workspace_id, update_data)
