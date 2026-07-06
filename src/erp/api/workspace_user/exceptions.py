from fastapi import status

from src.erp.core.exceptions import BaseAppError


class WorkspaceUserNotFoundError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace member not found or access record lookup failed.",
        )


class WorkspaceUserAlreadyInWorkspaceError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workspace user is already an active member of this workspace.",
        )
