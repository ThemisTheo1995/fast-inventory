from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.future import select
from sqlalchemy.orm import Session

from erp.api.auth.dependencies import get_current_active_user
from erp.api.auth.exceptions import InsufficientPermissionsError
from erp.api.auth.models import User
from erp.api.workspace.enums import InvitationStatusEnum
from erp.api.workspace.exceptions import WorkspaceNotFoundError
from erp.api.workspace.models import WorkspaceUser
from erp.database.base import get_db

ROLE_WEIGHTS = {
    "full_admin": 3,
    "edit_only": 2,
    "read_only": 1
}

# Map HTTP methods to the minimum required role weight
METHOD_WEIGHTS = {
    "GET": 1,      # read_only, edit_only, full_admin
    "OPTIONS": 1,
    "HEAD": 1,
    "POST": 2,     # edit_only, full_admin
    "PUT": 2,
    "PATCH": 2,
    "DELETE": 3    # full_admin only
}


def verify_workspace_access(
    request: Request,
    workspace_id: UUID,
    # CHECK 1: This sub-dependency guarantees an active, authenticated user
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)]
) -> WorkspaceUser:
    """
    Master dependency for workspace routes.
    Validates active session, workspace membership, and HTTP method permissions.
    """

    # CHECK 2: Validate the user actually belongs to this workspace
    query = select(WorkspaceUser).where(
        WorkspaceUser.user_id == current_user.id,
        WorkspaceUser.workspace_id == workspace_id,
        WorkspaceUser.status == InvitationStatusEnum.ACTIVE
    )
    workspace_link = db.execute(query).scalar_one_or_none()

    if not workspace_link:
        raise WorkspaceNotFoundError()

    # CHECK 3: Verify their role weight against the HTTP method
    required_weight = METHOD_WEIGHTS.get(request.method.upper(), 3)
    user_weight = ROLE_WEIGHTS.get(workspace_link.role.lower(), 0)

    if user_weight < required_weight:
        raise InsufficientPermissionsError()

    request.state.workspace_user = workspace_link

    return workspace_link
