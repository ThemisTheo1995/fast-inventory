import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.erp.api.base.models import BaseModel


class WorkspaceUserNote(BaseModel):
    __tablename__ = "workspace_user_notes"

    workspace_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspace_users.id"), index=True)

    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Relationships
    workspace_user: Mapped["WorkspaceUser"] = relationship("WorkspaceUser", back_populates="notes")
