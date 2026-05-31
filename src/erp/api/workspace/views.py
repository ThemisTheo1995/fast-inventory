from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from erp.api.auth.dependencies import get_current_active_user
from erp.api.auth.models import User
from erp.api.workspace.schemas import InviteMemberRequest, UpdateRoleRequest, WorkspaceMemberResponse
from erp.api.workspace.service import PermissionService
from erp.database.base import get_db

router = APIRouter()


@router.get("", response_model=list[WorkspaceMemberResponse])
def get_members(
    workspace_id: str,
    db: Annotated[Session, Depends(get_db)]
) -> list[WorkspaceMemberResponse]:

    service = PermissionService(db)

    return service.get_workspace_users(workspace_id)


@router.post("/invite", response_model=WorkspaceMemberResponse, status_code=status.HTTP_201_CREATED)
def invite_member(
    workspace_id: str,
    payload: InviteMemberRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> WorkspaceMemberResponse:

    service = PermissionService(db)
    return service.invite_member(
        workspace_id=workspace_id,
        email=payload.email,
        role=payload.role_id,
        actor_id=str(current_user.id)
    )


@router.patch("/{user_id}/role", status_code=status.HTTP_204_NO_CONTENT)
def change_role(
    workspace_id: str,
    user_id: str, payload: UpdateRoleRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> None:

    service = PermissionService(db)
    service.update_role(
        workspace_id=workspace_id,
        target_user_id=user_id,
        new_role=payload.role_id,
        actor_id=str(current_user.id)
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    workspace_id: str,
    user_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> None:

    service = PermissionService(db)
    service.remove_member(
        workspace_id=workspace_id,
        target_user_id=user_id,
        actor_id=str(current_user.id)
    )
