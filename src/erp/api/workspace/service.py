from uuid import UUID

from sqlalchemy.orm import Session

from erp.api.auth.models import User
from erp.api.workspace.exceptions import (
    UserAlreadyActiveMemberError,
    WorkspaceMemberNotFoundError,
    WorkspaceNotFoundError,
)
from erp.api.workspace.models import Workspace, WorkspaceUser
from erp.api.workspace.schemas.workspace import WorkspaceUpdate
from erp.api.workspace.schemas.workspace_user import WorkspaceUserResponse
from erp.api.workspace.utils import guard_against_self_action, guard_privilege_escalation, guard_rank_immunity


class WorkspaceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_workspace(self, workspace_id: UUID) -> Workspace:
        """Retrieves a workspace by its ID. Raises a 404 if it does not exist."""
        workspace = self.db.query(Workspace).filter(Workspace.id == workspace_id).first()

        if not workspace:
            raise WorkspaceNotFoundError()

        return workspace

    def update_workspace(self, workspace_id: UUID, update_data: WorkspaceUpdate) -> Workspace:
        """Updates an existing workspace based on provided fields."""

        workspace = self.get_workspace(workspace_id)

        update_dict = update_data.model_dump(exclude_unset=True)

        for key, value in update_dict.items():
            setattr(workspace, key, value)

        self.db.commit()
        self.db.refresh(workspace)

        return workspace


class WorkspaceUserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _get_active_workspace_user(self, workspace_id: str, user_id: str) -> WorkspaceUser:
        """Internal helper to dry up member lookups."""
        link = self.db.query(WorkspaceUser).filter(
            WorkspaceUser.workspace_id == workspace_id,
            WorkspaceUser.user_id == user_id,
            WorkspaceUser.is_deleted.is_(False)
        ).first()
        if not link:
            raise WorkspaceMemberNotFoundError()
        return link

    def get_workspace_users(self, workspace_id: str) -> list[dict]:
        """Fetch all non-deleted members linked to a specific workspace."""
        results = (
            self.db.query(WorkspaceUser, User)
            .join(User, WorkspaceUser.user_id == User.id)
            .filter(
                WorkspaceUser.workspace_id == workspace_id,
                WorkspaceUser.is_deleted.is_(False),
                User.is_deleted.is_(False)
            )
            .all()
        )

        members = []
        for ws_user, user in results:
            full_name = f"{user.first_name} {user.last_name}".strip() if user.first_name else None
            members.append(
                WorkspaceUserResponse(
                    id=str(user.id),
                    name=full_name,
                    email=user.email,
                    role_id=ws_user.role,
                    status=ws_user.status,
                )
            )

        return members

    def invite_member(self, workspace_id: str, email: str, role: str, actor_id: str) -> dict:
        """Invite a user while enforcing safeguards against privilege escalation."""
        actor = self._get_active_workspace_user(workspace_id, actor_id)

        guard_privilege_escalation(actor.role, role)

        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            user = User(email=email, hashed_password="", first_name="", last_name="", is_deleted=False)
            self.db.add(user)
            self.db.flush()

        existing_link = self.db.query(WorkspaceUser).filter(
            WorkspaceUser.workspace_id == workspace_id, WorkspaceUser.user_id == user.id
        ).first()

        if existing_link:
            if not existing_link.is_deleted:
                raise UserAlreadyActiveMemberError()
            existing_link.is_deleted = False
            existing_link.role = role
            existing_link.status = "pending"
            self.db.commit()
            return WorkspaceUserResponse(
                id=str(user.id),
                name=f"{user.first_name} {user.last_name}".strip() or None,
                email=email,
                role_id=role,
                status="pending",
            )

        new_member = WorkspaceUser(
            workspace_id=workspace_id,
            user_id=user.id,
            role=role,
            status="pending",
            is_deleted=False
        )
        self.db.add(new_member)
        self.db.commit()
        return WorkspaceUserResponse(
            id=str(user.id),
            name=None,
            email=email,
            role_id=role,
            status="pending",
        )

    def update_role(self, workspace_id: str, target_user_id: str, new_role: str, actor_id: str) -> None:
        """Modify an active member's role while strictly enforcing hierarchical safeguards."""

        guard_against_self_action(actor_id, target_user_id, is_eviction=False)

        actor = self._get_active_workspace_user(workspace_id, actor_id)
        target = self._get_active_workspace_user(workspace_id, target_user_id)

        guard_rank_immunity(actor.role, target.role)
        guard_privilege_escalation(actor.role, new_role)

        target.role = new_role
        self.db.commit()

    def remove_member(self, workspace_id: str, target_user_id: str, actor_id: str) -> None:
        """Soft-delete a member's workspace relationship record with authority validation."""

        guard_against_self_action(actor_id, target_user_id, is_eviction=True)

        actor = self._get_active_workspace_user(workspace_id, actor_id)
        target = self._get_active_workspace_user(workspace_id, target_user_id)

        guard_rank_immunity(actor.role, target.role)

        target.is_deleted = True
        self.db.commit()
