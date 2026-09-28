from fastapi import status

from src.erp.api.workspace.exceptions import (
    WorkspaceAlreadyExistsError,
    WorkspaceNotFoundError,
)


def test_workspace_not_found_error():
    """Verifies the status code and detail of WorkspaceNotFoundError."""
    exc = WorkspaceNotFoundError()

    assert exc.status_code == status.HTTP_403_FORBIDDEN
    assert exc.detail == "You do not have permission to access this workspace or it does not exist."


def test_workspace_already_exists_error():
    """Verifies the status code and detail of WorkspaceAlreadyExistsError."""
    exc = WorkspaceAlreadyExistsError()

    assert exc.status_code == status.HTTP_409_CONFLICT
    assert exc.detail == "A workspace with this email already exists."
