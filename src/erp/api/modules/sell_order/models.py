import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.erp.api.base.models import BaseModel
from src.erp.api.modules.sell_order.enums import SOStatusEnum


class SellOrder(BaseModel):
    __tablename__ = "sell_orders"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "so_number",
            name="uq_sell_orders_workspace_so_number",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id"), index=True, nullable=True)

    so_number: Mapped[str] = mapped_column(String(100), index=True)

    total_amount: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[SOStatusEnum] = mapped_column(
        Enum(
            SOStatusEnum,
            native_enum=False,
            length=50,
        ),
        default=SOStatusEnum.DRAFT,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="sell_orders")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="sell_orders")
    sell_order_lines: Mapped[list["SellOrderLine"]] = relationship(
        "SellOrderLine", back_populates="sell_order", cascade="all, delete-orphan"
    )


class SellOrderLine(BaseModel):
    __tablename__ = "sell_order_lines"

    sell_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sell_orders.id"), index=True)
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("items.id"), index=True, nullable=True)

    quantity: Mapped[int] = mapped_column(Integer)

    unit_cost: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    sell_order: Mapped["SellOrder"] = relationship("SellOrder", back_populates="sell_order_lines")
    item: Mapped["Item"] = relationship("Item")
