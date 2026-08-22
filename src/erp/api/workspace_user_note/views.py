from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session
from src.erp.api.workspace_user_note.schemas import (
    WorkspaceUserNoteCreate,
    WorkspaceUserNotePaginatedResponse,
    WorkspaceUserNoteResponse,
    WorkspaceUserNoteUpdate,
)
from src.erp.api.workspace_user_note.service import WorkspaceUserNoteService
from src.erp.database.base import get_db

router = APIRouter(prefix="/notes")


@router.post("", response_model=WorkspaceUserNoteResponse, status_code=status.HTTP_201_CREATED)
def create_note(
    request: Request,
    data: WorkspaceUserNoteCreate,
    db: Annotated[Session, Depends(get_db)],
) -> WorkspaceUserNoteResponse:

    workspace_user = request.state.workspace_user

    service = WorkspaceUserNoteService(db)
    return service.create_note(workspace_user.id, data)


@router.get("", response_model=WorkspaceUserNotePaginatedResponse)
def get_notes(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> WorkspaceUserNotePaginatedResponse:

    workspace_user = request.state.workspace_user

    service = WorkspaceUserNoteService(db)
    return service.get_notes(workspace_user.id, page, limit)


@router.get("/{note_id}", response_model=WorkspaceUserNoteResponse)
def get_note(request: Request, note_id: UUID, db: Annotated[Session, Depends(get_db)]) -> WorkspaceUserNoteResponse:
    workspace_user = request.state.workspace_user

    service = WorkspaceUserNoteService(db)
    return service.get_note(workspace_user.id, note_id)


@router.patch("/{note_id}", response_model=WorkspaceUserNoteResponse)
def update_note(
    request: Request,
    note_id: UUID,
    data: WorkspaceUserNoteUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> WorkspaceUserNoteResponse:
    workspace_user = request.state.workspace_user

    service = WorkspaceUserNoteService(db)
    return service.update_note(workspace_user.id, note_id, data)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    request: Request,
    note_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    workspace_user = request.state.workspace_user

    service = WorkspaceUserNoteService(db)
    service.delete_note(workspace_user.id, note_id)
