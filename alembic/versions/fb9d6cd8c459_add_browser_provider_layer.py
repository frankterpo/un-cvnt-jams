"""add_browser_provider_layer

Revision ID: fb9d6cd8c459
Revises: 6e8d6c64a2a3
Create Date: 2025-12-14 02:41:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'fb9d6cd8c459'
down_revision: Union[str, Sequence[str], None] = '6e8d6c64a2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Helper for cross-dialect JSON
JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB, "postgresql")


def upgrade() -> None:
    """Add browser provider layer tables and columns."""
    
    # 1. Create launch_groups table
    op.create_table('launch_groups',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('monthly_launch_cap', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('monthly_soft_cap', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 2. Create browser_providers table
    op.create_table('browser_providers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('kind', sa.String(50), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('max_profiles', sa.Integer(), nullable=True),
        sa.Column('max_launches_per_month', sa.Integer(), nullable=True),
        sa.Column('max_concurrent_sessions', sa.Integer(), nullable=True),
        sa.Column('config', JSON_TYPE, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_index('idx_browser_providers_active', 'browser_providers', ['is_active'], unique=False)
    
    # 3. Create browser_provider_profiles table
    op.create_table('browser_provider_profiles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('browser_provider_id', sa.Integer(), nullable=False),
        sa.Column('dummy_account_id', sa.Integer(), nullable=False),
        sa.Column('provider_profile_ref', sa.String(500), nullable=False),
        sa.Column('status', sa.String(50), server_default='active', nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['browser_provider_id'], ['browser_providers.id']),
        sa.ForeignKeyConstraint(['dummy_account_id'], ['dummy_accounts.id']),
        sa.PrimaryKeyConstraint('id')
    )
    # Unique constraint: one provider_profile_ref per provider
    op.create_index('idx_bpp_provider_profile_ref', 'browser_provider_profiles', 
                    ['browser_provider_id', 'provider_profile_ref'], unique=True)
    # Index for finding profiles for a dummy_account
    op.create_index('idx_bpp_dummy_provider', 'browser_provider_profiles', 
                    ['dummy_account_id', 'browser_provider_id'], unique=False)
    # Index for selecting candidate profiles (active, recent)
    op.create_index('idx_bpp_provider_status_used', 'browser_provider_profiles', 
                    ['browser_provider_id', 'status', 'last_used_at'], unique=False)
    
    # 4. Add launch_group_id and is_recurring_enabled to dummy_accounts
    with op.batch_alter_table('dummy_accounts') as batch_op:
        batch_op.add_column(sa.Column('launch_group_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('is_recurring_enabled', sa.Boolean(), server_default='true', nullable=False))
        batch_op.create_foreign_key('fk_dummy_accounts_launch_group', 'launch_groups', ['launch_group_id'], ['id'])
    
    # 5. Add browser provider columns to publishing_runs
    with op.batch_alter_table('publishing_runs') as batch_op:
        batch_op.add_column(sa.Column('browser_provider_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('browser_provider_profile_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('provider_session_ref', sa.String(500), nullable=True))
        batch_op.create_foreign_key('fk_runs_browser_provider', 'browser_providers', ['browser_provider_id'], ['id'])
        batch_op.create_foreign_key('fk_runs_browser_profile', 'browser_provider_profiles', ['browser_provider_profile_id'], ['id'])
    
    # Add indexes for provider analytics
    op.create_index('idx_runs_browser_provider', 'publishing_runs', ['browser_provider_id', 'created_at'], unique=False)
    op.create_index('idx_runs_browser_profile', 'publishing_runs', ['browser_provider_profile_id', 'created_at'], unique=False)
    
    # 6. Seed data
    # Insert default launch group
    op.execute("INSERT INTO launch_groups (name, monthly_launch_cap) VALUES ('Default Group', 100)")
    
    # Insert browser providers
    op.execute("""
        INSERT INTO browser_providers (code, display_name, kind, max_profiles, max_launches_per_month) VALUES
        ('GOLOGIN', 'GoLogin', 'antidetect', 3, 100),
        ('NOVNC', 'noVNC', 'vnc', NULL, NULL)
    """)


def downgrade() -> None:
    """Remove browser provider layer."""
    
    # Drop indexes on publishing_runs
    op.drop_index('idx_runs_browser_profile', table_name='publishing_runs')
    op.drop_index('idx_runs_browser_provider', table_name='publishing_runs')
    
    # Remove columns from publishing_runs
    with op.batch_alter_table('publishing_runs') as batch_op:
        batch_op.drop_constraint('fk_runs_browser_profile', type_='foreignkey')
        batch_op.drop_constraint('fk_runs_browser_provider', type_='foreignkey')
        batch_op.drop_column('provider_session_ref')
        batch_op.drop_column('browser_provider_profile_id')
        batch_op.drop_column('browser_provider_id')
    
    # Remove columns from dummy_accounts
    with op.batch_alter_table('dummy_accounts') as batch_op:
        batch_op.drop_constraint('fk_dummy_accounts_launch_group', type_='foreignkey')
        batch_op.drop_column('is_recurring_enabled')
        batch_op.drop_column('launch_group_id')
    
    # Drop browser_provider_profiles
    op.drop_index('idx_bpp_provider_status_used', table_name='browser_provider_profiles')
    op.drop_index('idx_bpp_dummy_provider', table_name='browser_provider_profiles')
    op.drop_index('idx_bpp_provider_profile_ref', table_name='browser_provider_profiles')
    op.drop_table('browser_provider_profiles')
    
    # Drop browser_providers
    op.drop_index('idx_browser_providers_active', table_name='browser_providers')
    op.drop_table('browser_providers')
    
    # Drop launch_groups
    op.drop_table('launch_groups')
