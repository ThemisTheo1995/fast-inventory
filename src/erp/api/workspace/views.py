from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.erp.api.auth.dependencies import get_current_active_user
from src.erp.api.auth.models import User
from src.erp.api.workspace.schemas.workspace import (
    WorkspaceResponse,
    WorkspaceUpdate,
)
from src.erp.api.workspace.schemas.workspace_user import (
    InviteWorkspaceUserRequest,
    UpdateWorkspaceUserRoleRequest,
    WorkspaceUserResponse,
)
from src.erp.api.workspace.service import WorkspaceService, WorkspaceUserService
from src.erp.database.base import get_db

router = APIRouter()


# ------------------------------
# Workspace
# ------------------------------


@router.get("", response_model=WorkspaceResponse)
def get_workspace(workspace_id: UUID, db: Annotated[Session, Depends(get_db)]) -> WorkspaceResponse:

    service = WorkspaceService(db)

    return service.get_workspace(workspace_id)


@router.patch("", response_model=WorkspaceResponse)
def update_workspace(
    workspace_id: UUID, update_data: WorkspaceUpdate, db: Annotated[Session, Depends(get_db)]
) -> WorkspaceResponse:

    service = WorkspaceService(db)

    return service.update_workspace(workspace_id, update_data)


# ------------------------------
# WorkspaceUsers
# ------------------------------


@router.get("/members", response_model=list[WorkspaceUserResponse])
def get_members(workspace_id: UUID, db: Annotated[Session, Depends(get_db)]) -> list[WorkspaceUserResponse]:

    service = WorkspaceUserService(db)

    return service.get_workspace_users(workspace_id)


@router.post("/members/invite", response_model=WorkspaceUserResponse, status_code=status.HTTP_201_CREATED)
def add_member(
    workspace_id: UUID,
    payload: InviteWorkspaceUserRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> WorkspaceUserResponse:

    service = WorkspaceUserService(db)
    return service.invite_member(
        workspace_id=workspace_id, email=payload.email, role=payload.role_id, actor_id=current_user.id
    )


@router.patch("/members/{user_id}/role", status_code=status.HTTP_204_NO_CONTENT)
def change_member_role(
    workspace_id: UUID,
    user_id: UUID,
    payload: UpdateWorkspaceUserRoleRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:

    service = WorkspaceUserService(db)
    service.update_role(
        workspace_id=workspace_id, target_user_id=user_id, new_role=payload.role_id, actor_id=current_user.id
    )


@router.delete("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    workspace_id: UUID,
    user_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:

    service = WorkspaceUserService(db)
    service.remove_member(workspace_id=workspace_id, target_user_id=user_id, actor_id=current_user.id)
