"""Add is_whitelisted in User model

Revision ID: 9390410ca880
Revises: d6226f8904a6
Create Date: 2026-09-18 14:22:00.179041

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9390410ca880'
down_revision: Union[str, Sequence[str], None] = 'd6226f8904a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add column as nullable initially
    op.add_column('users', sa.Column('is_whitelisted', sa.Boolean(), nullable=True))

    # 2. Update all existing users to True
    op.execute("UPDATE users SET is_whitelisted = TRUE")

    # 3. Enforce nullable=False and set default to False for new users at DB level
    op.alter_column(
        'users',
        'is_whitelisted',
        nullable=False,
        server_default=sa.false(),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'is_whitelisted')
