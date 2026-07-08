from fastapi import status

from src.erp.core.exceptions import BaseAppError


class WorkspaceNotFoundError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this workspace or it does not exist.",
        )
