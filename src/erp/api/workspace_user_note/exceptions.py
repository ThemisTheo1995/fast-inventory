from fastapi import status

from erp.core.exceptions import BaseAppError


class WorkspaceUserNoteNotFoundError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace user note not found or access record lookup failed.",
        )
