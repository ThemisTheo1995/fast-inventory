import uuid

from sqlalchemy import CheckConstraint, Enum as SQLAlchemyEnum, ForeignKey, Integer
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.erp.api.base.models import BaseModel
from src.erp.api.modules.inventory.enums import OrderType


class Inventory(BaseModel):
    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint("quantity_allocated >= 0", name="chk_inventory_allocated_positive"),
        CheckConstraint("quantity_on_order >= 0", name="chk_inventory_on_order_positive"),
        CheckConstraint("quantity_on_hand >= 0", name="chk_inventory_on_hand_positive"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id"), unique=True, index=True)

    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    quantity_allocated: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    quantity_on_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Relationships
    item: Mapped["Item"] = relationship("Item", back_populates="inventory")

    @hybrid_property
    def quantity_available(self) -> int:
        """Stock available to pack and ship right now."""
        return self.quantity_on_hand - self.quantity_allocated

    @hybrid_property
    def expected_available(self) -> int:
        """Stock available to sell (including incoming POs)."""
        return (self.quantity_on_hand + self.quantity_on_order) - self.quantity_allocated


class StockMovement(BaseModel):
    __tablename__ = "inventory_stock_movements"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id"), index=True)

    quantity_change: Mapped[int] = mapped_column(Integer)

    reference_type: Mapped[OrderType] = mapped_column(SQLAlchemyEnum(OrderType), nullable=False)

    reference_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    # Relationships
    item: Mapped["Item"] = relationship("Item", back_populates="stock_movements")
