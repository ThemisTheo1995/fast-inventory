import uuid
from enum import StrEnum

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.erp.api.base.models import BaseModel


class ProviderType(StrEnum):
    AMAZON = "amazon"
    EBAY = "ebay"
    SHOPIFY = "shopify"


class Integration(BaseModel):
    __tablename__ = "workspace_integrations"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False
    )

    provider_type: Mapped[ProviderType] = mapped_column(String(50), nullable=False)

    credentials: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (UniqueConstraint("workspace_id", "provider_type", name="uq_workspace_provider"),)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="integrations")
