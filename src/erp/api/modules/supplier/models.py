import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.erp.api.base.models import BaseModel


class Supplier(BaseModel):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("workspace_id", "email", name="uix_workspace_supplier_email"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="suppliers")
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship("PurchaseOrder", back_populates="supplier")
