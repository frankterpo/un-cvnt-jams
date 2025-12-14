"""add_updated_at_to_post_assets

Revision ID: 6e8d6c64a2a3
Revises: 01c7e01ae621
Create Date: 2025-12-14 02:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6e8d6c64a2a3'
down_revision: Union[str, Sequence[str], None] = '01c7e01ae621'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('publishing_post_assets', 
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False)
    )


def downgrade() -> None:
    op.drop_column('publishing_post_assets', 'updated_at')
