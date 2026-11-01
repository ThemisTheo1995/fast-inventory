import uuid

import pytest

from erp.api.workspace.models import Workspace
from erp.api.workspace_user.enums import InvitationStatusEnum, WorkspaceRoleEnum
from erp.api.workspace_user.models import WorkspaceUser


@pytest.fixture
async def another_workspace_user(db_session, tst_user):
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Another Test Workspace",
        email=f"another-{uuid.uuid4().hex[:8]}@example.com",
        is_deleted=False,
    )

    db_session.add(workspace)
    await db_session.flush()

    workspace_user = WorkspaceUser(
        id=uuid.uuid4(),
        user_id=tst_user.id,
        workspace_id=workspace.id,
        status=InvitationStatusEnum.ACTIVE,
        is_deleted=False,
        role=WorkspaceRoleEnum.FULL_ADMIN,
    )

    db_session.add(workspace_user)
    await db_session.commit()
    await db_session.refresh(workspace_user)

    return workspace_user
