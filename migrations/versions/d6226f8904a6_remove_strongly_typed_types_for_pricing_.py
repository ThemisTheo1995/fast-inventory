"""Remove strongly typed types for Pricing plans and capitalize existing plan names

Revision ID: d6226f8904a6
Revises: 3be9370467af
Create Date: 2026-09-05 11:37:32.502669

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd6226f8904a6'
down_revision: Union[str, Sequence[str], None] = '3be9370467af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Cast column to VARCHAR and transform existing values to UPPERCASE in a single step
    op.alter_column(
        'pricing_plans',
        'name',
        existing_type=postgresql.ENUM('GROWTH', 'PRO', 'ENTERPRISE', 'CUSTOM', name='planname'),
        type_=sa.Enum('GROWTH', 'PRO', 'ENTERPRISE', 'CUSTOM', name='planname', native_enum=False, length=50),
        existing_nullable=False,
        postgresql_using='UPPER(name::text)',
    )

    # 2. Clean up the native PostgreSQL enum type
    sa.Enum(name='planname').drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Re-create the native PostgreSQL enum type
    planname_enum = postgresql.ENUM('GROWTH', 'PRO', 'ENTERPRISE', 'CUSTOM', name='planname')
    planname_enum.create(op.get_bind(), checkfirst=True)

    # 2. Revert column back to native ENUM
    op.alter_column(
        'pricing_plans',
        'name',
        existing_type=sa.Enum('GROWTH', 'PRO', 'ENTERPRISE', 'CUSTOM', name='planname', native_enum=False, length=50),
        type_=planname_enum,
        existing_nullable=False,
        postgresql_using='name::planname',
    )
