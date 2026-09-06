import re

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from erp.api.base.models import BaseModel


class Workspace(BaseModel):
    __tablename__ = "workspaces"

    # Basic Info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=True, unique=True)

    # Location
    country: Mapped[str] = mapped_column(String(100), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=True)
    address_line1: Mapped[str] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str] = mapped_column(String(255), nullable=True)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=True)

    # Relationships
    workspace_users: Mapped[list["WorkspaceUser"]] = relationship("WorkspaceUser", back_populates="workspace")

    items: Mapped[list["Item"]] = relationship("Item", back_populates="workspace")
    customers: Mapped[list["Customer"]] = relationship("Customer", back_populates="workspace")
    suppliers: Mapped[list["Supplier"]] = relationship("Supplier", back_populates="workspace")
    sell_orders: Mapped[list["SellOrder"]] = relationship("SellOrder", back_populates="workspace")
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship("PurchaseOrder", back_populates="workspace")

    @validates("email")
    def validate_email(self, _key: str, email_address: str) -> str:
        """Basic email format validation using regex."""

        if not email_address:
            msg = "Email address cannot be empty."
            raise ValueError(msg)

        if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email_address):
            msg = f"Invalid email address format: {email_address}"
            raise ValueError(msg)

        return email_address.lower()

    @validates("phone_number")
    def validate_phone_number(self, _key: str, phone: str) -> str:
        """Basic phone number validation using regex for E.164 format."""
        if not phone:
            msg = "Phone number cannot be empty."
            raise ValueError(msg)

        if not re.match(r"^\+?[1-9]\d{1,14}$", phone):
            msg = f"Invalid phone number format: {phone}. Must be in E.164 format."
            raise ValueError(msg)

        return phone
