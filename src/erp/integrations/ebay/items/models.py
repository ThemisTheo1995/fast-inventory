from decimal import Decimal

from sqlalchemy import ARRAY, Enum as SQLEnum, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from erp.api.base.models import BaseModel
from erp.integrations.ebay.items.enums import EbayItemStatus


class EbayItem(BaseModel):
    __tablename__ = "ebay_items"

    # eBay's specific ID (Needs to be a string as eBay item IDs can be very large)
    external_id: Mapped[str] = mapped_column(String, unique=True, index=True)

    # ERP Linkage
    sku: Mapped[str | None] = mapped_column(String, index=True, nullable=True)

    # Item Details
    title: Mapped[str] = mapped_column(String)

    description: Mapped[str] = mapped_column(String)

    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    currency: Mapped[str] = mapped_column(String(3))

    quantity: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[EbayItemStatus] = mapped_column(
        SQLEnum(EbayItemStatus, native_enum=False, length=50),
        default=EbayItemStatus.DRAFT,
        index=True
    )

    images: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        default=list,
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<EbayItem(sku='{self.sku}', title='{self.title}', price={self.price})>"
