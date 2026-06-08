import re
import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from erp.api.base.models import BaseModel
from erp.api.workspace.enums import InvitationStatusEnum, WorkspaceRoleEnum


class Workspace(BaseModel):
    __tablename__ = "workspaces"

    # Basic Info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=True, unique=True)

    # Location
    country: Mapped[str] = mapped_column(String(100), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=True)
    address_line1: Mapped[str] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str] = mapped_column(String(255), nullable=True)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=True)

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

    # ----------------------------
    # Validators
    # ----------------------------

    @validates('email')
    def validate_email(self, _key: str, email_address: str) -> str:
        """Basic email format validation using regex."""

        if not email_address:
            msg = "Email address cannot be empty."
            raise ValueError(msg)

        if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email_address):
            msg = f"Invalid email address format: {email_address}"
            raise ValueError(msg)

        return email_address.lower()

    @validates('phone_number')
    def validate_phone_number(self, _key: str, phone: str) -> str:
        """Basic phone number validation using regex for E.164 format."""
        if not phone:
            msg = "Phone number cannot be empty."
            raise ValueError(msg)

        if not re.match(r"^\+?[1-9]\d{1,14}$", phone):
            msg = f"Invalid phone number format: {phone}. Must be in E.164 format."
            raise ValueError(msg)

        return phone


class WorkspaceUser(BaseModel):
    """
    Represents a tenant (workspace/user).
    """
    __tablename__ = "workspace_users"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String,
        default=WorkspaceRoleEnum.READ_ONLY.value,
        server_default="read_only",
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String,
        default=InvitationStatusEnum.PENDING.value,
        server_default="pending",
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "workspace_id", name="uq_workspace_and_user"),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="workspaces")
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="workspace_users")
