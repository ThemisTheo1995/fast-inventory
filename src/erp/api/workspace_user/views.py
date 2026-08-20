from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from src.erp.api.workspace_user.schemas import (
    UserResponse,
    UserUpdateRequest,
    WorkspaceUserInviteRequest,
    WorkspaceUserResponse,
    WorkspaceUserUpdateRequest,
)
from src.erp.api.workspace_user.service import WorkspaceUserService
from src.erp.database.base import get_db

router = APIRouter()


@router.get("/me")
def me(request: Request) -> dict:
    workspace_user = request.state.workspace_user
    current_user = workspace_user.user

    return {
        "id": current_user.id,
        "workspace_user_id": workspace_user.id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "workspace_id": workspace_user.workspace_id,
        "role": workspace_user.role,
        "status": workspace_user.status,
    }


@router.patch("/me", response_model=UserResponse)
def update_me(request: Request, data: UserUpdateRequest, db: Annotated[Session, Depends(get_db)]) -> UserResponse:

    workspace_user = request.state.workspace_user
    current_user = workspace_user.user

    return UserResponse.model_validate(
        WorkspaceUserService(db).update_user(
            current_user,
            data,
        )
    )


@router.get("/workspace-users", response_model=list[WorkspaceUserResponse])
def get_workspace_users(workspace_id: UUID, db: Annotated[Session, Depends(get_db)]) -> list[WorkspaceUserResponse]:

    service = WorkspaceUserService(db)

    return service.get_workspace_users(workspace_id)


@router.get("/workspace-users/{workspace_user_id}", response_model=WorkspaceUserResponse)
def get_workspace_user(workspace_user_id: UUID, db: Annotated[Session, Depends(get_db)]) -> WorkspaceUserResponse:

    service = WorkspaceUserService(db)

    return service.get_workspace_user(workspace_user_id)


@router.post("/workspace-users/invite", response_model=WorkspaceUserResponse, status_code=status.HTTP_201_CREATED)
def add_workspace_user(
    request: Request, data: WorkspaceUserInviteRequest, db: Annotated[Session, Depends(get_db)]
) -> WorkspaceUserResponse:

    workspace_user = request.state.workspace_user
    service = WorkspaceUserService(db)

    return service.invite_workspace_user(data, actor=workspace_user)


@router.patch("/workspace-users/{workspace_user_id}", status_code=status.HTTP_200_OK)
def update_workspace_user(
    request: Request, workspace_user_id: UUID, data: WorkspaceUserUpdateRequest, db: Annotated[Session, Depends(get_db)]
) -> WorkspaceUserResponse:

    workspace_user = request.state.workspace_user
    service = WorkspaceUserService(db)

    return service.update_workspace_user(data=data, target_id=workspace_user_id, actor=workspace_user)
