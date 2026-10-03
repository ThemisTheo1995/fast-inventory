import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.api.base.models import BaseModel


class Customer(BaseModel):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("workspace_id", "email", name="uix_workspace_customer_email"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    first_name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))

    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="customers")
    sell_orders: Mapped[list["SellOrder"]] = relationship("SellOrder", back_populates="customer")
