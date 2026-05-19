import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.api.models.base import BaseModel


class User(BaseModel):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    first_name: Mapped[str | None] = mapped_column(String)
    last_name: Mapped[str | None] = mapped_column(String)

    supplier_users: Mapped[list["SupplierUser"]] = relationship(
        "SupplierUser",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    ebay_integration_users: Mapped[list["EbayIntegrationUser"]] = relationship(
        "EbayIntegrationUser", back_populates="user", cascade="all, delete-orphan"
    )


class SupplierUser(BaseModel):
    """The link between a User and a Supplier (Workspace)."""
    __tablename__ = "supplier_users"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "supplier_id", name="uq_user_supplier"),
    )

    user: Mapped["User"] = relationship("User", back_populates="supplier_users")
    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="supplier_users")
