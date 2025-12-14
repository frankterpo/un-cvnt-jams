"""add_updated_at_to_run_events

Revision ID: 7a4afa0ec5ab
Revises: fb9d6cd8c459
Create Date: 2025-12-14 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a4afa0ec5ab'
down_revision: Union[str, Sequence[str], None] = 'fb9d6cd8c459'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('publishing_run_events', 
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False)
    )


def downgrade() -> None:
    op.drop_column('publishing_run_events', 'updated_at')
