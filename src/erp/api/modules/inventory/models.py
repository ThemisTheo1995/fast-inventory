import uuid

from sqlalchemy import Enum as SQLAlchemyEnum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.erp.api.base.models import BaseModel
from src.erp.api.modules.inventory.enums import OrderType


class Inventory(BaseModel):
    __tablename__ = "inventory"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id"), unique=True, index=True)
    quantity_available: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Relationships
    item: Mapped["Item"] = relationship("Item", back_populates="inventory")


class StockMovement(BaseModel):
    __tablename__ = "inventory_stock_movements"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id"), index=True)

    quantity_change: Mapped[int] = mapped_column(Integer)

    reference_type: Mapped[OrderType] = mapped_column(SQLAlchemyEnum(OrderType), nullable=False)

    reference_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    # Relationships
    item: Mapped["Item"] = relationship("Item", back_populates="stock_movements")
