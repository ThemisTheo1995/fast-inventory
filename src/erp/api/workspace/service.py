from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.workspace.exceptions import (
    WorkspaceNotFoundError,
)
from erp.api.workspace.models import Workspace
from erp.api.workspace.schemas import WorkspaceUpdate


class WorkspaceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_workspace(self, workspace_id: UUID) -> Workspace:
        """Retrieves a workspace by its ID. Raises a 404 if it does not exist."""
        stmt = select(Workspace).where(Workspace.id == workspace_id)
        result = await self.db.execute(stmt)
        workspace = result.scalar_one_or_none()

        if not workspace:
            raise WorkspaceNotFoundError()

        return workspace

    async def update_workspace(self, workspace_id: UUID, update_data: WorkspaceUpdate) -> Workspace:
        """Updates an existing workspace based on provided fields."""

        workspace = await self.get_workspace(workspace_id)

        update_dict = update_data.model_dump(exclude_unset=True)

        for key, value in update_dict.items():
            setattr(workspace, key, value)

        self.db.add(workspace)
        await self.db.commit()
        await self.db.refresh(workspace)

        return workspace
