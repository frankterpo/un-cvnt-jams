"""add_launch_group_quotas

Revision ID: ae7c00e9a89c
Revises: 7a4afa0ec5ab
Create Date: 2025-12-14 04:17:43.744406

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ae7c00e9a89c'
down_revision: Union[str, Sequence[str], None] = '7a4afa0ec5ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('launch_groups', sa.Column('max_runs_per_day', sa.Integer(), nullable=True))
    op.add_column('launch_groups', sa.Column('max_concurrent_runs', sa.Integer(), nullable=True))
    op.add_column('launch_groups', sa.Column('max_runs_per_month', sa.Integer(), server_default='100', nullable=False))
    
    # Counters
    op.add_column('launch_groups', sa.Column('current_month_run_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('launch_groups', sa.Column('current_day_run_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('launch_groups', sa.Column('current_concurrent_runs', sa.Integer(), server_default='0', nullable=False))
    
    # Windows
    op.add_column('launch_groups', sa.Column('month_window_start', sa.DateTime(timezone=True), nullable=True))
    op.add_column('launch_groups', sa.Column('day_window_start', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('launch_groups', 'day_window_start')
    op.drop_column('launch_groups', 'month_window_start')
    op.drop_column('launch_groups', 'current_concurrent_runs')
    op.drop_column('launch_groups', 'current_day_run_count')
    op.drop_column('launch_groups', 'current_month_run_count')
    op.drop_column('launch_groups', 'max_runs_per_month')
    op.drop_column('launch_groups', 'max_concurrent_runs')
    op.drop_column('launch_groups', 'max_runs_per_day')
