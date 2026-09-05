from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.erp.api.workspace_user_note.exceptions import WorkspaceUserNoteNotFoundError
from src.erp.api.workspace_user_note.models import WorkspaceUserNote
from src.erp.api.workspace_user_note.schemas import (
    WorkspaceUserNoteCreate,
    WorkspaceUserNotePaginatedResponse,
    WorkspaceUserNoteUpdate,
)


class WorkspaceUserNoteService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get_active_note(self, workspace_user_id: UUID, note_id: UUID) -> WorkspaceUserNote:
        """Securely fetch a workspace_user_note belonging to this specific workspace membership."""
        stmt = select(WorkspaceUserNote).where(
            WorkspaceUserNote.workspace_user_id == workspace_user_id,
            WorkspaceUserNote.id == note_id,
            WorkspaceUserNote.is_deleted.is_(False),
        )
        result = await self.db.execute(stmt)
        workspace_user_note = result.scalar_one_or_none()

        if not workspace_user_note:
            raise WorkspaceUserNoteNotFoundError()
        return workspace_user_note

    async def create_note(self, workspace_user_id: UUID, data: WorkspaceUserNoteCreate) -> WorkspaceUserNote:
        workspace_user_note = WorkspaceUserNote(
            workspace_user_id=workspace_user_id,
            **data.model_dump(),
        )
        self.db.add(workspace_user_note)
        await self.db.commit()
        await self.db.refresh(workspace_user_note)
        return workspace_user_note

    async def get_notes(
        self, workspace_user_id: UUID, page: int = 1, limit: int = 20
    ) -> WorkspaceUserNotePaginatedResponse:
        base_query = select(WorkspaceUserNote).where(
            WorkspaceUserNote.workspace_user_id == workspace_user_id,
            WorkspaceUserNote.is_deleted.is_(False),
        )

        base_query = base_query.order_by(WorkspaceUserNote.is_pinned.desc(), WorkspaceUserNote.updated_at.desc())

        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        skip = (page - 1) * limit
        items_result = await self.db.execute(base_query.offset(skip).limit(limit))
        items = list(items_result.scalars().all())

        return WorkspaceUserNotePaginatedResponse(items=items, total=total)

    async def get_note(self, workspace_user_id: UUID, note_id: UUID) -> WorkspaceUserNote:
        return await self._get_active_note(workspace_user_id, note_id)

    async def update_note(
        self, workspace_user_id: UUID, note_id: UUID, data: WorkspaceUserNoteUpdate
    ) -> WorkspaceUserNote:
        workspace_user_note = await self._get_active_note(workspace_user_id, note_id)
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(workspace_user_note, key, value)

        self.db.add(workspace_user_note)
        await self.db.commit()
        await self.db.refresh(workspace_user_note)
        return workspace_user_note

    async def delete_note(self, workspace_user_id: UUID, note_id: UUID) -> None:
        workspace_user_note = await self._get_active_note(workspace_user_id, note_id)
        workspace_user_note.soft_delete()
        await self.db.commit()
