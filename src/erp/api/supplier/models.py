from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.api.base.models import BaseModel


class Supplier(BaseModel):
    """
    Represents a tenant (company/user) in your SaaS.
    """
    __tablename__ = "suppliers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    supplier_users: Mapped[list["SupplierUser"]] = relationship(
        "SupplierUser",
        back_populates="supplier",
        cascade="all, delete-orphan"
    )

    ebay_integrations: Mapped[list["EbayIntegration"]] = relationship(
        "EbayIntegration",
        back_populates="supplier",
        cascade="all, delete-orphan"
    )
