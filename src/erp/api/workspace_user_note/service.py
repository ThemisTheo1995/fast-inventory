from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from src.erp.api.workspace_user_note.exceptions import WorkspaceUserNoteNotFoundError
from src.erp.api.workspace_user_note.models import WorkspaceUserNote
from src.erp.api.workspace_user_note.schemas import (
    WorkspaceUserNoteCreate,
    WorkspaceUserNotePaginatedResponse,
    WorkspaceUserNoteUpdate,
)


class WorkspaceUserNoteService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _get_active_note(self, workspace_user_id: UUID, note_id: UUID) -> WorkspaceUserNote:
        """Securely fetch a workspace_user_note belonging to this specific workspace membership."""
        stmt = select(WorkspaceUserNote).where(
            WorkspaceUserNote.workspace_user_id == workspace_user_id,
            WorkspaceUserNote.id == note_id,
            WorkspaceUserNote.is_deleted.is_(False),
        )
        workspace_user_note = self.db.execute(stmt).scalar_one_or_none()

        if not workspace_user_note:
            raise WorkspaceUserNoteNotFoundError()
        return workspace_user_note

    def create_note(self, workspace_user_id: UUID, data: WorkspaceUserNoteCreate) -> WorkspaceUserNote:
        workspace_user_note = WorkspaceUserNote(
            workspace_user_id=workspace_user_id,
            **data.model_dump(),
        )
        self.db.add(workspace_user_note)
        self.db.commit()
        self.db.refresh(workspace_user_note)
        return workspace_user_note

    def get_notes(self, workspace_user_id: UUID, page: int = 1, limit: int = 20) -> WorkspaceUserNotePaginatedResponse:
        base_query = select(WorkspaceUserNote).where(
            WorkspaceUserNote.workspace_user_id == workspace_user_id,
            WorkspaceUserNote.is_deleted.is_(False),
        )

        base_query = base_query.order_by(WorkspaceUserNote.is_pinned.desc(), WorkspaceUserNote.updated_at.desc())

        count_query = select(func.count()).select_from(base_query.subquery())
        total = self.db.execute(count_query).scalar_one()

        skip = (page - 1) * limit
        items = list(self.db.execute(base_query.offset(skip).limit(limit)).scalars().all())

        return WorkspaceUserNotePaginatedResponse(items=items, total=total)

    def get_note(self, workspace_user_id: UUID, note_id: UUID) -> WorkspaceUserNote:
        return self._get_active_note(workspace_user_id, note_id)

    def update_note(self, workspace_user_id: UUID, note_id: UUID, data: WorkspaceUserNoteUpdate) -> WorkspaceUserNote:
        workspace_user_note = self._get_active_note(workspace_user_id, note_id)
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(workspace_user_note, key, value)

        self.db.add(workspace_user_note)
        self.db.commit()
        self.db.refresh(workspace_user_note)
        return workspace_user_note

    def delete_note(self, workspace_user_id: UUID, note_id: UUID) -> None:
        workspace_user_note = self._get_active_note(workspace_user_id, note_id)
        workspace_user_note.soft_delete()
        self.db.commit()
