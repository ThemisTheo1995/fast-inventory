import uuid

from sqlalchemy import CheckConstraint, Enum as SQLAlchemyEnum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.api.base.models import BaseModel
from erp.api.modules.inventory.enums import StockMovementType


class Inventory(BaseModel):
    __tablename__ = "inventory"
    __table_args__ = (
        UniqueConstraint("workspace_id", "item_id", "bin_id", name="uix_workspace_item_bin"),
        CheckConstraint("quantity_on_hand >= 0", name="chk_inventory_on_hand_positive"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id"), index=True)
    bin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bins.id"), index=True)

    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Relationships
    item: Mapped["Item"] = relationship("Item", back_populates="inventory_items")
    bin: Mapped["Bin"] = relationship("Bin", back_populates="inventory_items")


class StockMovement(BaseModel):
    __tablename__ = "inventory_stock_movements"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id"), index=True)
    bin_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bins.id"), nullable=True, index=True)

    quantity_change: Mapped[int] = mapped_column(Integer)

    reference_type: Mapped[StockMovementType] = mapped_column(
        SQLAlchemyEnum(StockMovementType, native_enum=False, length=50), nullable=False
    )
    reference_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    item: Mapped["Item"] = relationship("Item", back_populates="stock_movements")
    bin: Mapped["Bin | None"] = relationship("Bin", lazy="noload")
