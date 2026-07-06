import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.erp.api.base.models import BaseModel


class SellOrder(BaseModel):
    __tablename__ = "sell_orders"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id"), index=True, nullable=True)

    order_number: Mapped[str] = mapped_column(String(100), index=True)

    total_amount: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50))

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="sell_orders")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="sell_orders")
    sell_order_lines: Mapped[list["SellOrderLine"]] = relationship(
        "SellOrderLine", back_populates="sell_order", cascade="all, delete-orphan"
    )


class SellOrderLine(BaseModel):
    __tablename__ = "sell_order_lines"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sell_orders.id"), index=True)
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("items.id"), index=True, nullable=True)

    quantity: Mapped[int] = mapped_column(Integer)

    unit_price: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    sell_order: Mapped["SellOrder"] = relationship("SellOrder", back_populates="sell_order_lines")
    item: Mapped["Item"] = relationship("Item")
