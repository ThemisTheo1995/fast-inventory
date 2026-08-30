import uuid

import pytest

from src.erp.api.workspace.exceptions import WorkspaceNotFoundError
from src.erp.api.workspace.schemas import WorkspaceUpdate
from src.erp.api.workspace.service import WorkspaceService


def test_get_workspace_success(db_session, seed_workspace):
    """Verifies fetching an existing workspace returns the expected model."""
    service = WorkspaceService(db_session)

    workspace = service.get_workspace(seed_workspace)

    assert workspace is not None
    assert workspace.id == seed_workspace
    assert workspace.name == "Primary Test Workspace"
    assert workspace.email == f"primary-{seed_workspace}@test.com"


def test_get_workspace_not_found(db_session):
    """Verifies WorkspaceNotFoundError is raised when the workspace ID does not exist."""
    service = WorkspaceService(db_session)
    random_id = uuid.uuid4()

    with pytest.raises(WorkspaceNotFoundError):
        service.get_workspace(random_id)


def test_update_workspace_success(db_session, seed_workspace):
    """Verifies fields are updated, committed, and returned properly."""
    service = WorkspaceService(db_session)
    update_data = WorkspaceUpdate(name="Updated Workspace Name")

    updated = service.update_workspace(seed_workspace, update_data)

    assert updated.id == seed_workspace
    assert updated.name == "Updated Workspace Name"


def test_update_workspace_not_found(db_session):
    """Verifies updating a non-existent workspace raises WorkspaceNotFoundError."""
    service = WorkspaceService(db_session)
    random_id = uuid.uuid4()
    update_data = WorkspaceUpdate(name="Should Fail")

    with pytest.raises(WorkspaceNotFoundError):
        service.update_workspace(random_id, update_data)
