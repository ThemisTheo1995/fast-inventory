import uuid

import pytest

from src.erp.api.auth.models import User
from src.erp.api.workspace_user.enums import InvitationStatusEnum, WorkspaceRoleEnum
from src.erp.api.workspace_user.models import WorkspaceUser


@pytest.fixture
async def target_user(db_session) -> User:
    """Seeds a secondary user record to test modifications or additions."""
    user = User(
        id=uuid.uuid4(),
        email="target-member@company.com",
        first_name="Target",
        last_name="Member",
        hashed_password="",
        is_deleted=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def target_workspace_user(db_session, seed_workspace, target_user) -> WorkspaceUser:
    """Seeds a targeted link between the new user and our globally seeded workspace."""
    ws_user = WorkspaceUser(
        id=uuid.uuid4(),
        user_id=target_user.id,
        workspace_id=seed_workspace,
        role=WorkspaceRoleEnum.READ_ONLY,
        status=InvitationStatusEnum.ACTIVE,
        is_deleted=False,
    )
    db_session.add(ws_user)
    await db_session.commit()
    return ws_user
