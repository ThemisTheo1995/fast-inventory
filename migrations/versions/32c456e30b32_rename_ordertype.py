
"""Rename OrderType

Revision ID: 32c456e30b32
Revises: 4128d2d85d8e
Create Date: 2026-10-25 15:37:14.094629
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "32c456e30b32"
down_revision: Union[str, Sequence[str], None] = "4128d2d85d8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Replace the PostgreSQL OrderType enum with a VARCHAR column."""

    op.alter_column(
        "inventory_stock_movements",
        "reference_type",
        existing_type=postgresql.ENUM(
            "SELL_ORDER",
            "PURCHASE_ORDER",
            "MANUAL_ADJUSTMENT",
            name="ordertype",
        ),
        type_=sa.String(length=50),
        existing_nullable=False,
        postgresql_using="reference_type::text",
    )

    # Drop the old PostgreSQL enum after its column dependency is removed.
    op.execute("DROP TYPE IF EXISTS ordertype")


def downgrade() -> None:
    """Restore the PostgreSQL OrderType enum."""

    # BIN_TRANSFER cannot be represented by the old enum.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM inventory_stock_movements
                WHERE reference_type = 'BIN_TRANSFER'
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade: BIN_TRANSFER values exist in inventory_stock_movements.reference_type';
            END IF;
        END
        $$;
        """
    )

    # Recreate the old enum type.
    ordertype = postgresql.ENUM(
        "SELL_ORDER",
        "PURCHASE_ORDER",
        "MANUAL_ADJUSTMENT",
        name="ordertype",
        create_type=False,
    )
    ordertype.create(op.get_bind(), checkfirst=True)

    op.alter_column(
        "inventory_stock_movements",
        "reference_type",
        existing_type=sa.String(length=50),
        type_=ordertype,
        existing_nullable=False,
        postgresql_using="reference_type::ordertype",
    )
