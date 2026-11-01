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
    base_price: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    barcode_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Global Commercial Metrics
    quantity_on_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    quantity_allocated: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="items")
    inventory_items: Mapped[list["Inventory"]] = relationship(
        "Inventory", back_populates="item", cascade="all, delete-orphan", lazy="noload"
    )
    stock_movements: Mapped[list["StockMovement"]] = relationship("StockMovement", back_populates="item", lazy="noload")

    @property
    def total_quantity_on_hand(self) -> int:
        """Sum of physical stock across all warehouse bins."""
        return sum(inv.quantity_on_hand for inv in self.inventory_items if not inv.is_deleted)
