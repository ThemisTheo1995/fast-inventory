import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.erp.api.base.models import BaseModel
from src.erp.api.workspace.enums import WorkspaceRoleEnum
from src.erp.api.workspace_user.enums import InvitationStatusEnum


class WorkspaceUser(BaseModel):
    """
    Represents a tenant (workspace/user).
    """

    __tablename__ = "workspace_users"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"),
        index=True,
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String, default=WorkspaceRoleEnum.READ_ONLY.value, server_default="read_only", nullable=False
    )

    status: Mapped[str] = mapped_column(
        String, default=InvitationStatusEnum.PENDING.value, server_default="pending", nullable=False
    )

    __table_args__ = (UniqueConstraint("user_id", "workspace_id", name="uq_workspace_and_user"),)

    user: Mapped["User"] = relationship("User", back_populates="workspaces")
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="workspace_users")
