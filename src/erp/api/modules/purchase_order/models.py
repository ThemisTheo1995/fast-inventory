import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.erp.api.base.models import BaseModel
from src.erp.api.modules.purchase_order.enums import POStatusEnum


class PurchaseOrder(BaseModel):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "po_number",
            name="uq_purchase_orders_workspace_po_number",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("suppliers.id"), index=True, nullable=True)

    po_number: Mapped[str] = mapped_column(String(100), index=True)

    total_amount: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[POStatusEnum] = mapped_column(
        Enum(
            POStatusEnum,
            native_enum=False,
            length=50,
        ),
        default=POStatusEnum.DRAFT,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="purchase_orders")
    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="purchase_orders")
    purchase_order_lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        "PurchaseOrderLine", back_populates="purchase_order", cascade="all, delete-orphan"
    )


class PurchaseOrderLine(BaseModel):
    __tablename__ = "purchase_order_lines"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("items.id"), index=True, nullable=True)

    quantity: Mapped[int] = mapped_column(Integer)
    unit_cost: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    purchase_order: Mapped["PurchaseOrder"] = relationship("PurchaseOrder", back_populates="purchase_order_lines")
    item: Mapped["Item"] = relationship("Item")
