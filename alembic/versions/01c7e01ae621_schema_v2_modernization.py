"""schema_v2_modernization

Revision ID: 01c7e01ae621
Revises: 79e40a331383
Create Date: 2025-12-14 01:57:21.896158

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy import String, Integer, DateTime, Boolean, Text, JSON

# revision identifiers, used by Alembic.
revision: str = '01c7e01ae621'
down_revision: Union[str, Sequence[str], None] = '79e40a331383'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema with data preservation."""
    
    # Helper for JSON type
    JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB, "postgresql")
    
    # 1. Create Lookup Tables First (Users, Platforms)
    # ------------------------------------------------
    users_table = op.create_table('users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('role', sa.String(length=50), server_default="operator", nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by_user_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    
    platforms_table = op.create_table('platforms',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('max_caption_len', sa.Integer(), nullable=True),
        sa.Column('config', JSON_TYPE, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )

    # 2. Seed Data
    # ------------
    # Seed Admin User
    op.execute("INSERT INTO users (email, role, first_name) VALUES ('admin@example.com', 'admin', 'System')")
    
    # Seed Platforms
    op.bulk_insert(platforms_table, [
        {'code': 'instagram', 'display_name': 'Instagram', 'slug': 'instagram', 'is_active': True},
        {'code': 'tiktok', 'display_name': 'TikTok', 'slug': 'tiktok', 'is_active': True},
        {'code': 'youtube', 'display_name': 'YouTube', 'slug': 'youtube', 'is_active': True},
    ])

    # 3. Create Campaigns (Needed for Assets FK)
    # ------------------------------------------
    op.create_table('campaigns',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('platform_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['deleted_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['platform_id'], ['platforms.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_campaigns_user_platform_created', 'campaigns', ['user_id', 'platform_id', 'created_at'], unique=False)

    # Create Default Legacy Campaign linked to Admin and Instagram (ID 1)
    op.execute("""
        INSERT INTO campaigns (user_id, platform_id, name, status, created_at, updated_at)
        SELECT id, 1, 'Legacy Campaign', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM users WHERE email='admin@example.com'
    """)

    # 4. Migrate ACCOUNTS -> DUMMY_ACCOUNTS
    # -------------------------------------
    op.rename_table('accounts', 'dummy_accounts')
    # op.rename_column used to be here, but moved to batch block for sqlite safety?
    # Actually rename_table is structural. Columns should be altered in batch.
    
    with op.batch_alter_table('dummy_accounts') as batch_op:
        batch_op.alter_column('primary_contact_email', new_column_name='username')
        batch_op.add_column(sa.Column('platform_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('display_name', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False))
        batch_op.add_column(sa.Column('environment', sa.String(length=50), server_default='prod', nullable=False))
        batch_op.add_column(sa.Column('config', JSON_TYPE, nullable=True))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('deleted_by_user_id', sa.Integer(), nullable=True))
        
        batch_op.create_foreign_key('fk_dummy_accounts_platform', 'platforms', ['platform_id'], ['id'])
        batch_op.create_foreign_key('fk_dummy_accounts_user', 'users', ['deleted_by_user_id'], ['id'])
    
    # Update existing rows to default platform (Instagram=1)
    op.execute("UPDATE dummy_accounts SET platform_id = 1 WHERE platform_id IS NULL")
    
    # Add indexes/constraints
    # Indexes can be done outside batch usually, but constraints inside?
    # 'username' effectively holds old email or we can copy 'name' to it.
    op.execute("UPDATE dummy_accounts SET username = name WHERE username IS NULL")
    
    with op.batch_alter_table('dummy_accounts') as batch_op:
         batch_op.alter_column('username', nullable=False)
    
    op.create_index('idx_dummy_accounts_platform_active', 'dummy_accounts', ['platform_id', 'is_active'], unique=False)

    
    # 5. Migrate UPLOADED_ASSETS -> ASSETS
    # ------------------------------------
    op.rename_table('uploaded_assets', 'assets')
    
    with op.batch_alter_table('assets') as batch_op:
        batch_op.alter_column('original_filename', new_column_name='original_name')
        
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('campaign_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('deleted_by_user_id', sa.Integer(), nullable=True))
        
        batch_op.drop_column('uploaded_by_first_name')
        batch_op.drop_column('uploaded_by_last_name')
        batch_op.drop_column('uploaded_by_email')
        batch_op.drop_column('metadata_json') 
    
    # Link assets to default admin and campaign
    op.execute("UPDATE assets SET user_id = (SELECT id FROM users WHERE email='admin@example.com')")
    op.execute("UPDATE assets SET campaign_id = (SELECT id FROM campaigns LIMIT 1)")
    
    with op.batch_alter_table('assets') as batch_op:
        batch_op.drop_column('account_id')
        batch_op.create_foreign_key('fk_assets_user', 'users', ['user_id'], ['id'])
        batch_op.create_foreign_key('fk_assets_campaign', 'campaigns', ['campaign_id'], ['id'])
        batch_op.create_foreign_key('fk_assets_del_user', 'users', ['deleted_by_user_id'], ['id'])
    
    op.create_index('idx_assets_campaign_status_created', 'assets', ['campaign_id', 'status', 'created_at'], unique=False)


    # 6. Archive Old Publishing Tables
    # --------------------------------
    # We rename them to `legacy_*` so data is not lost, but they are out of the way.
    op.rename_table('publishing_run_posts', 'legacy_publishing_run_posts')
    op.rename_table('publishing_run_post_content', 'legacy_publishing_run_post_content')

    # 7. Create New Schema Tables
    # ---------------------------
    
    # DummyAccountPersona
    op.create_table('dummy_account_personas',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('dummy_account_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('short_label', sa.String(length=50), nullable=True),
        sa.Column('tone', sa.String(length=255), nullable=True),
        sa.Column('archetype', sa.String(length=255), nullable=True),
        sa.Column('target_audience', sa.Text(), nullable=True),
        sa.Column('topics', sa.Text(), nullable=True),
        sa.Column('style_guide', sa.Text(), nullable=True),
        sa.Column('posting_goals', sa.Text(), nullable=True),
        sa.Column('config', JSON_TYPE, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['deleted_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['dummy_account_id'], ['dummy_accounts.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dummy_account_id')
    )

    # PublishingRuns
    op.create_table('publishing_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('dummy_account_id', sa.Integer(), nullable=False),
        sa.Column('platform_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('idempotency_key', sa.String(length=255), nullable=True),
        sa.Column('trace_id', sa.String(length=255), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('priority', sa.Integer(), server_default='0', nullable=False),
        sa.Column('environment', sa.String(length=50), server_default='prod', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
        sa.ForeignKeyConstraint(['dummy_account_id'], ['dummy_accounts.id'], ),
        sa.ForeignKeyConstraint(['platform_id'], ['platforms.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('idempotency_key')
    )
    op.create_index('idx_runs_campaign_created', 'publishing_runs', ['campaign_id', 'created_at'], unique=False)
    op.create_index('idx_runs_dummy_created', 'publishing_runs', ['dummy_account_id', 'created_at'], unique=False)
    op.create_index('idx_runs_queue_platform_sched_priority', 'publishing_runs', ['platform_id', 'scheduled_at', 'priority', 'id'], unique=False, postgresql_where=sa.text("lower(status) IN ('pending', 'scheduled')"), sqlite_where=sa.text("lower(status) IN ('pending', 'scheduled')"))
    op.create_index('idx_runs_status_created', 'publishing_runs', ['status', 'created_at'], unique=False)

    # PublishingPosts
    op.create_table('publishing_posts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('publishing_run_id', sa.Integer(), nullable=False),
        sa.Column('dummy_account_id', sa.Integer(), nullable=False),
        sa.Column('platform_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='pending', nullable=False),
        sa.Column('external_post_id', sa.String(length=255), nullable=True),
        sa.Column('sequence_no', sa.Integer(), server_default='1', nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['dummy_account_id'], ['dummy_accounts.id'], ),
        sa.ForeignKeyConstraint(['platform_id'], ['platforms.id'], ),
        sa.ForeignKeyConstraint(['publishing_run_id'], ['publishing_runs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_posts_dummy_created_at', 'publishing_posts', ['dummy_account_id', 'created_at'], unique=False)
    op.create_index('idx_posts_run_sequence', 'publishing_posts', ['publishing_run_id', 'sequence_no'], unique=False)
    op.create_index('idx_posts_status_created_at', 'publishing_posts', ['status', 'created_at'], unique=False)

    # PublishingPostAssets
    op.create_table('publishing_post_assets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('publishing_post_id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), server_default='1', nullable=False),
        sa.Column('is_cover', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
        sa.ForeignKeyConstraint(['publishing_post_id'], ['publishing_posts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_post_assets_asset', 'publishing_post_assets', ['asset_id'], unique=False)
    op.create_index('idx_post_assets_post_position', 'publishing_post_assets', ['publishing_post_id', 'position'], unique=False)

    # PublishingPostContent
    op.create_table('publishing_post_content',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('publishing_post_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', JSON_TYPE, nullable=True),
        sa.Column('language', sa.String(length=10), nullable=True),
        sa.Column('tone', sa.String(length=50), nullable=True),
        sa.Column('extra_payload', JSON_TYPE, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['publishing_post_id'], ['publishing_posts.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('publishing_post_id')
    )

    # PublishingRunEvents
    op.create_table('publishing_run_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('publishing_run_id', sa.Integer(), nullable=False),
        sa.Column('publishing_post_id', sa.Integer(), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('old_status', sa.String(length=50), nullable=True),
        sa.Column('new_status', sa.String(length=50), nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.Column('worker_id', sa.String(length=100), nullable=True),
        sa.Column('trace_id', sa.String(length=255), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('payload', JSON_TYPE, nullable=True),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['publishing_post_id'], ['publishing_posts.id'], ),
        sa.ForeignKeyConstraint(['publishing_run_id'], ['publishing_runs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_run_events_error_created', 'publishing_run_events', ['error_code', 'created_at'], unique=False)
    op.create_index('idx_run_events_post_created', 'publishing_run_events', ['publishing_post_id', 'created_at'], unique=False)
    op.create_index('idx_run_events_run_created', 'publishing_run_events', ['publishing_run_id', 'created_at'], unique=False)
    op.create_index('idx_run_events_type_created', 'publishing_run_events', ['event_type', 'created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema (Destructive for new data)."""
    # Inverse operations - simplified
    
    op.drop_table('publishing_run_events')
    op.drop_table('publishing_post_content')
    op.drop_table('publishing_post_assets')
    op.drop_table('publishing_posts')
    op.drop_table('publishing_runs')
    op.drop_table('dummy_account_personas')
    
    with op.batch_alter_table('assets') as batch_op:
        batch_op.drop_constraint('fk_assets_user', type_='foreignkey')
        batch_op.drop_constraint('fk_assets_campaign', type_='foreignkey')
        batch_op.drop_constraint('fk_assets_del_user', type_='foreignkey')
        batch_op.drop_column('deleted_by_user_id')
        batch_op.drop_column('campaign_id')
        batch_op.drop_column('user_id')
        batch_op.add_column(sa.Column('account_id', sa.Integer(), nullable=True))
        batch_op.alter_column('original_name', new_column_name='original_filename')
    
    op.rename_table('assets', 'uploaded_assets')
    
    with op.batch_alter_table('dummy_accounts') as batch_op:
        batch_op.drop_constraint('fk_dummy_accounts_platform', type_='foreignkey')
        batch_op.drop_constraint('fk_dummy_accounts_user', type_='foreignkey')
        batch_op.drop_column('deleted_by_user_id')
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('config')
        batch_op.drop_column('environment')
        batch_op.drop_column('is_active')
        batch_op.drop_column('display_name')
        batch_op.drop_column('platform_id')
        batch_op.alter_column('username', new_column_name='primary_contact_email', nullable=True)
    
    op.rename_table('dummy_accounts', 'accounts')
    
    op.rename_table('legacy_publishing_run_posts', 'publishing_run_posts')
    op.rename_table('legacy_publishing_run_post_content', 'publishing_run_post_content')
    
    op.drop_table('campaigns')
    op.drop_table('platforms')
    op.drop_table('users')
