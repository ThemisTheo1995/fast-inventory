from uuid import UUID

from sqlalchemy.orm import Session

from src.erp.api.workspace.exceptions import (
    WorkspaceNotFoundError,
)
from src.erp.api.workspace.models import Workspace
from src.erp.api.workspace.schemas import WorkspaceUpdate


class WorkspaceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_workspace(self, workspace_id: UUID) -> Workspace:
        """Retrieves a workspace by its ID. Raises a 404 if it does not exist."""
        workspace = self.db.query(Workspace).filter(Workspace.id == workspace_id).first()

        if not workspace:
            raise WorkspaceNotFoundError()

        return workspace

    def update_workspace(self, workspace_id: UUID, update_data: WorkspaceUpdate) -> Workspace:
        """Updates an existing workspace based on provided fields."""

        workspace = self.get_workspace(workspace_id)

        update_dict = update_data.model_dump(exclude_unset=True)

        for key, value in update_dict.items():
            setattr(workspace, key, value)

        self.db.commit()
        self.db.refresh(workspace)

        return workspace
