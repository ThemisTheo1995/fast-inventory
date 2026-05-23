import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.api.base.models import BaseModel


class Workspace(BaseModel):
    """
    Represents a tenant (workspace/user).
    """
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    # Relationships
    workspace_users: Mapped[list["WorkspaceUser"]] = relationship(
        "WorkspaceUser",
        back_populates="workspace",
        cascade="all, delete-orphan"
    )
    integrations: Mapped[list["Integration"]] = relationship(
        "Integration",
        back_populates="workspace",
        cascade="all, delete-orphan"
    )


class WorkspaceUser(BaseModel):
    __tablename__ = "workspace_users"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "workspace_id", name="uq_workspace_and_user"),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="workspaces")
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="workspace_users")
