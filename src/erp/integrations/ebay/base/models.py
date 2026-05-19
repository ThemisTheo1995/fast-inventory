import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, ForeignKeyConstraint, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.api.models.base import BaseModel
from erp.integrations.ebay.base.enum import EbayPermissionRole


class EbayIntegration(BaseModel):
    """
    Stores OAuth credentials for specific integrations.
    """
    __tablename__ = "ebay_integrations"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # The short-lived token (used for API requests)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)

    # The long-lived token (used to get new access_tokens)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)

    # When the access_token expires
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Metadata like the eBay "username" or Shopify "shop_url"
    platform_account_id: Mapped[str | None] = mapped_column(String(255))

    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="ebay_integrations")


class EbayIntegrationUser(BaseModel):
    """Integration Access: Links User to EbayIntegration + stores their Role."""
    __tablename__ = "ebay_integration_users"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), index=True)
    ebay_integration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ebay_integrations.id", ondelete="CASCADE"), index=True)

    role: Mapped[EbayPermissionRole] = mapped_column(
        Enum(EbayPermissionRole, name="permission_role_enum"),
        default=EbayPermissionRole.READER,
        nullable=False
    )

    # COMPOSITE FOREIGN KEY: This prevents a user from gaining integration access
    # unless (user_id, supplier_id) ALREADY exists inside the supplier_users table.
    __table_args__ = (
        # 1. Enforce that a user can only have ONE role assignment per integration record
        UniqueConstraint("user_id", "ebay_integration_id", name="uq_user_ebay_integration"),

        # 2. COMPOSITE FOREIGN KEY: Ensures user belongs to the supplier workspace first.
        ForeignKeyConstraint(
            ["user_id", "supplier_id"],
            ["supplier_users.user_id", "supplier_users.supplier_id"],
            ondelete="CASCADE"
        ),
    )

    user: Mapped["User"] = relationship("User", back_populates="ebay_integration_users")
