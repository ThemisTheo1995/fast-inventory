from fastapi import status

from erp.api.workspace_user_note.exceptions import (
    WorkspaceUserNoteNotFoundError,
)
from erp.core.exceptions import BaseAppError


def test_workspace_user_note_not_found_error():
    error = WorkspaceUserNoteNotFoundError()

    assert isinstance(error, BaseAppError)
    assert error.status_code == status.HTTP_404_NOT_FOUND
    assert error.detail == ("Workspace user note not found or access record lookup failed.")
