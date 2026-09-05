from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.erp.api.auth.models import User
from src.erp.api.workspace_user.enums import InvitationStatusEnum
from src.erp.api.workspace_user.exceptions import WorkspaceUserAlreadyInWorkspaceError, WorkspaceUserNotFoundError
from src.erp.api.workspace_user.models import WorkspaceUser
from src.erp.api.workspace_user.schemas import (
    UserUpdateRequest,
    WorkspaceUserInviteRequest,
    WorkspaceUserResponse,
    WorkspaceUserUpdateRequest,
)
from src.erp.api.workspace_user.utils import guard_against_self_action, guard_privilege_escalation, guard_rank_immunity


class WorkspaceUserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get_active_workspace_user(self, workspace_id: UUID, workspace_user_id: UUID) -> WorkspaceUser:
        """Internal helper to dry up member lookups."""
        stmt = (
            select(WorkspaceUser)
            .options(selectinload(WorkspaceUser.user))
            .where(
                WorkspaceUser.workspace_id == workspace_id,
                WorkspaceUser.id == workspace_user_id,
                WorkspaceUser.is_deleted.is_(False),
            )
        )
        result = await self.db.execute(stmt)
        link = result.scalar_one_or_none()
        if not link:
            raise WorkspaceUserNotFoundError()
        return link

    async def get_workspace_users(self, workspace_id: UUID) -> list[WorkspaceUserResponse]:
        """Fetch all non-deleted workspace users linked to a specific workspace."""
        stmt = (
            select(WorkspaceUser, User)
            .join(User, WorkspaceUser.user_id == User.id)
            .where(
                WorkspaceUser.workspace_id == workspace_id,
                WorkspaceUser.is_deleted.is_(False),
                User.is_deleted.is_(False),
            )
            .order_by(WorkspaceUser.status.desc())
        )
        result = await self.db.execute(stmt)
        results = result.all()

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

    async def get_workspace_user(self, workspace_user_id: UUID) -> WorkspaceUserResponse:
        """Fetch a single non-deleted workspace user."""
        stmt = (
            select(WorkspaceUser, User)
            .join(User, WorkspaceUser.user_id == User.id)
            .where(
                WorkspaceUser.id == workspace_user_id,
                WorkspaceUser.is_deleted.is_(False),
                User.is_deleted.is_(False),
            )
        )
        result = await self.db.execute(stmt)
        row = result.first()

        if not row:
            raise WorkspaceUserNotFoundError()

        ws_user, user = row

        return WorkspaceUserResponse(
            id=str(ws_user.id),
            workspace_id=str(ws_user.workspace_id),
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            role=ws_user.role,
            status=ws_user.status,
        )

    async def invite_workspace_user(
        self, data: WorkspaceUserInviteRequest, actor: WorkspaceUser
    ) -> WorkspaceUserResponse:
        """Invite a workspace user while enforcing safeguards against privilege escalation."""
        role = data.role
        email = data.email

        guard_privilege_escalation(actor.role, role)

        is_existing_user = True
        user_stmt = select(User).where(User.email == email)
        user_result = await self.db.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        if not user:
            user = User(email=email, hashed_password="", first_name="", last_name="", is_deleted=False)
            self.db.add(user)
            await self.db.flush()
            is_existing_user = False

        ws_user_stmt = select(WorkspaceUser).where(
            WorkspaceUser.workspace_id == actor.workspace_id, WorkspaceUser.user_id == user.id
        )
        ws_user_result = await self.db.execute(ws_user_stmt)
        workspace_user = ws_user_result.scalar_one_or_none()

        workspace_user_status = InvitationStatusEnum.ACTIVE if is_existing_user else InvitationStatusEnum.PENDING

        if workspace_user:
            if not workspace_user.is_deleted:
                raise WorkspaceUserAlreadyInWorkspaceError()
            workspace_user.is_deleted = False
            workspace_user.role = role
            workspace_user.status = workspace_user_status
            await self.db.commit()

            return WorkspaceUserResponse(
                id=str(workspace_user.id),
                name=f"{user.first_name} {user.last_name}".strip() or None,
                email=email,
                role=role,
                status=workspace_user_status,
            )

        new_workspace_user = WorkspaceUser(
            workspace_id=actor.workspace_id, user_id=user.id, role=role, status=workspace_user_status, is_deleted=False
        )
        self.db.add(new_workspace_user)
        await self.db.commit()
        await self.db.refresh(new_workspace_user)

        return WorkspaceUserResponse(
            id=str(new_workspace_user.user_id),
            name=None,
            email=email,
            role=role,
            status=workspace_user_status,
        )

    async def update_workspace_user(
        self, data: WorkspaceUserUpdateRequest, target_id: UUID, actor: WorkspaceUser
    ) -> WorkspaceUserResponse:
        target = await self._get_active_workspace_user(actor.workspace_id, target_id)

        guard_rank_immunity(actor.role, target.role)

        update_data = data.model_dump(exclude_unset=True)

        if "role" in update_data:
            is_eviction = target_id == actor.id and data.is_deleted is True
            guard_against_self_action(actor.id, target_id, is_eviction=is_eviction)
            guard_privilege_escalation(actor.role, update_data["role"])

        for key, value in update_data.items():
            setattr(target, key, value)

        self.db.add(target)
        await self.db.commit()
        await self.db.refresh(target)

        return WorkspaceUserResponse(
            id=str(target.id),
            name=None,
            email=target.user.email,
            role=target.role,
            status=target.status,
        )

    async def update_user(self, user: User, data: UserUpdateRequest) -> User:
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(user, key, value)

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return user
