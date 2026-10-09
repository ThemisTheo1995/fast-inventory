import uuid
from datetime import datetime
from typing import ClassVar

from sqlalchemy import Boolean, DateTime, False_, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.api.base.models import BaseModel


class User(BaseModel):
    __tablename__ = "users"
    __audited__: ClassVar[bool] = False

    hashed_password: Mapped[str | None] = mapped_column(String, nullable=True)
    is_whitelisted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=False_(), nullable=False)
    last_password_reset_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_email_change_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    first_name: Mapped[str | None] = mapped_column(String)
    last_name: Mapped[str | None] = mapped_column(String)

    # Relationships
    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )

    workspaces: Mapped[list["WorkspaceUser"]] = relationship("WorkspaceUser", back_populates="user")


class UserSession(BaseModel):
    __tablename__ = "user_sessions"
    __audited__: ClassVar[bool] = False

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    session_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship("User", back_populates="sessions")
