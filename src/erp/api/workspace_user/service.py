from uuid import UUID

from sqlalchemy.orm import Session

from src.erp.api.auth.models import User
from src.erp.api.workspace_user.exceptions import WorkspaceUserAlreadyInWorkspaceError, WorkspaceUserNotFoundError
from src.erp.api.workspace_user.models import WorkspaceUser
from src.erp.api.workspace_user.schemas import (
    WorkspaceUserInviteRequest,
    WorkspaceUserResponse,
    WorkspaceUserUpdateRequest,
)
from src.erp.api.workspace_user.utils import guard_against_self_action, guard_privilege_escalation, guard_rank_immunity


class WorkspaceUserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _get_active_workspace_user(self, workspace_id: UUID, workspace_user_id: UUID) -> WorkspaceUser:
        """Internal helper to dry up member lookups."""
        link = (
            self.db.query(WorkspaceUser)
            .filter(
                WorkspaceUser.workspace_id == workspace_id,
                WorkspaceUser.id == workspace_user_id,
                WorkspaceUser.is_deleted.is_(False),
            )
            .first()
        )
        if not link:
            raise WorkspaceUserNotFoundError()
        return link

    def get_workspace_users(self, workspace_id: str) -> list[dict]:
        """Fetch all non-deleted workspace users linked to a specific workspace."""
        results = (
            self.db.query(WorkspaceUser, User)
            .join(User, WorkspaceUser.user_id == User.id)
            .filter(
                WorkspaceUser.workspace_id == workspace_id,
                WorkspaceUser.is_deleted.is_(False),
                User.is_deleted.is_(False),
            )
            .order_by(WorkspaceUser.status.desc())
            .all()
        )

        workspace_users = []
        for ws_user, user in results:
            full_name = f"{user.first_name} {user.last_name}".strip() if user.first_name else None
            workspace_users.append(
                WorkspaceUserResponse(
                    id=str(ws_user.id),
                    name=full_name,
                    email=user.email,
                    role=ws_user.role,
                    status=ws_user.status,
                )
            )

        return workspace_users

    def invite_workspace_user(self, data: WorkspaceUserInviteRequest, actor: WorkspaceUser) -> dict:
        """Invite a workspace user while enforcing safeguards against privilege escalation."""
        role = data.role
        email = data.email

        guard_privilege_escalation(actor.role, role)

        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            user = User(email=email, hashed_password="", first_name="", last_name="", is_deleted=False)
            self.db.add(user)
            self.db.flush()

        workspace_user = (
            self.db.query(WorkspaceUser)
            .filter(WorkspaceUser.workspace_id == actor.workspace_id, WorkspaceUser.user_id == user.id)
            .first()
        )

        if workspace_user:
            if not workspace_user.is_deleted:
                raise WorkspaceUserAlreadyInWorkspaceError()
            workspace_user.is_deleted = False
            workspace_user.role = role
            workspace_user.status = "pending"
            self.db.commit()
            return WorkspaceUserResponse(
                id=str(workspace_user.id),
                name=f"{user.first_name} {user.last_name}".strip() or None,
                email=email,
                role=role,
                status="pending",
            )

        new_workspace_user = WorkspaceUser(
            workspace_id=actor.workspace_id, user_id=user.id, role=role, status="pending", is_deleted=False
        )
        self.db.add(new_workspace_user)
        self.db.commit()
        self.db.refresh(new_workspace_user)

        return WorkspaceUserResponse(
            id=str(new_workspace_user.user_id),
            name=None,
            email=email,
            role=role,
            status="pending",
        )

    def update_workspace_user(
        self, data: WorkspaceUserUpdateRequest, target_id: UUID, actor: WorkspaceUser
    ) -> WorkspaceUserResponse:

        is_eviction = target_id == actor.id and data.is_deleted is True

        # 1. Guard checks
        guard_against_self_action(actor.id, target_id, is_eviction=is_eviction)

        target = self._get_active_workspace_user(actor.workspace_id, target_id)

        guard_rank_immunity(actor.role, target.role)

        # 2. Extract ONLY the fields the client sent
        update_data = data.model_dump(exclude_unset=True)

        if "role" in update_data:
            guard_privilege_escalation(actor.role, update_data["role"])

        # 3. Apply all changes
        for key, value in update_data.items():
            setattr(target, key, value)

        self.db.add(target)
        self.db.commit()
        self.db.refresh(target)

        return WorkspaceUserResponse(
            id=str(target.id),
            name=None,
            email=target.user.email,
            role=target.role,
            status=target.status,
        )
