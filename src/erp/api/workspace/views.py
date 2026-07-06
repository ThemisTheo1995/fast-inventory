from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.erp.api.workspace.schemas import (
    WorkspaceResponse,
    WorkspaceUpdate,
)
from src.erp.api.workspace.service import WorkspaceService
from src.erp.database.base import get_db

router = APIRouter()


@router.get("", response_model=WorkspaceResponse)
def get_workspace(workspace_id: UUID, db: Annotated[Session, Depends(get_db)]) -> WorkspaceResponse:

    service = WorkspaceService(db)

    return service.get_workspace(workspace_id)


@router.patch("", response_model=WorkspaceResponse)
def update_workspace(
    workspace_id: UUID, update_data: WorkspaceUpdate, db: Annotated[Session, Depends(get_db)]
) -> WorkspaceResponse:

    service = WorkspaceService(db)

    return service.update_workspace(workspace_id, update_data)
