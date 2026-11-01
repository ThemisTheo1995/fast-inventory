import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.api.base.models import BaseModel


class Bin(BaseModel):
    __tablename__ = "bins"
    __table_args__ = (UniqueConstraint("workspace_id", "code", name="uix_workspace_bin_code"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    code: Mapped[str] = mapped_column(String(50), index=True)  # e.g., "A-01-03"
    zone: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g., "Warehouse A"

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    inventory_items: Mapped[list["Inventory"]] = relationship("Inventory", back_populates="bin", lazy="noload")
