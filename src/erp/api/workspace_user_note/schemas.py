from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceUserNoteBase(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    content: str = Field(..., min_length=0)
    is_pinned: bool = False
    color: str | None = Field(default=None, max_length=50)


class WorkspaceUserNoteCreate(WorkspaceUserNoteBase):
    pass


class WorkspaceUserNoteUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    content: str | None = Field(default=None, min_length=0)
    is_pinned: bool | None = None
    color: str | None = Field(default=None, max_length=50)


class WorkspaceUserNoteResponse(WorkspaceUserNoteBase):
    id: UUID
    workspace_user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceUserNotePaginatedResponse(BaseModel):
    items: list[WorkspaceUserNoteResponse]
    total: int
