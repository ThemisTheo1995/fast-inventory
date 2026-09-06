import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.api.base.models import BaseModel


class Item(BaseModel):
    __tablename__ = "items"
    __table_args__ = (UniqueConstraint("workspace_id", "sku", name="uix_workspace_sku"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    sku: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(255))
    base_price: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="items")
    inventory: Mapped["Inventory"] = relationship(
        "Inventory", back_populates="item", uselist=False, cascade="all, delete-orphan"
    )
    stock_movements: Mapped[list["StockMovement"]] = relationship("StockMovement", back_populates="item", lazy="noload")
