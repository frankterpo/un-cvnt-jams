"""ORM models for the social agent (Schema v2)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    JSON,
    func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent.db.base import Base

# Utility for cross-dialect JSON support (JSONB on Postgres, JSON on SQLite)
JSON_VARIANT = JSON().with_variant(JSONB, "postgresql")


class User(Base):
    """Represents a human user/operator of the system."""
    
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="operator", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    campaigns: Mapped[List["Campaign"]] = relationship(back_populates="user", foreign_keys="[Campaign.user_id]")
    assets: Mapped[List["Asset"]] = relationship(back_populates="user", foreign_keys="Asset.user_id")
    publishing_runs: Mapped[List["PublishingRun"]] = relationship(back_populates="user")


class Platform(Base):
    """Lookup table for social platforms (Instagram, TikTok, YouTube)."""
    
    __tablename__ = "platforms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # instagram, tiktok
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_caption_len: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Use variant for config
    config: Mapped[Optional[dict]] = mapped_column(JSON_VARIANT, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    campaigns: Mapped[List["Campaign"]] = relationship(back_populates="platform")
    dummy_accounts: Mapped[List["DummyAccount"]] = relationship(back_populates="platform")
    publishing_runs: Mapped[List["PublishingRun"]] = relationship(back_populates="platform")
    publishing_posts: Mapped[List["PublishingPost"]] = relationship(back_populates="platform")


class LaunchGroup(Base):
    """Groups dummy accounts for shared quota management."""
    
    __tablename__ = "launch_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    monthly_launch_cap: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    monthly_soft_cap: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    dummy_accounts: Mapped[List["DummyAccount"]] = relationship(back_populates="launch_group")


class BrowserProvider(Base):
    """Browser automation provider (GoLogin, noVNC, etc.)."""
    
    __tablename__ = "browser_providers"

    __table_args__ = (
        Index("idx_browser_providers_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)  # antidetect, vnc, headless
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    max_profiles: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_launches_per_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_concurrent_sessions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    config: Mapped[Optional[dict]] = mapped_column(JSON_VARIANT, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    profiles: Mapped[List["BrowserProviderProfile"]] = relationship(back_populates="provider")
    publishing_runs: Mapped[List["PublishingRun"]] = relationship(back_populates="browser_provider")


class BrowserProviderProfile(Base):
    """Maps dummy_accounts to provider-specific profiles."""
    
    __tablename__ = "browser_provider_profiles"

    __table_args__ = (
        Index("idx_bpp_provider_profile_ref", "browser_provider_id", "provider_profile_ref", unique=True),
        Index("idx_bpp_dummy_provider", "dummy_account_id", "browser_provider_id"),
        Index("idx_bpp_provider_status_used", "browser_provider_id", "status", "last_used_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    browser_provider_id: Mapped[int] = mapped_column(ForeignKey("browser_providers.id"), nullable=False)
    dummy_account_id: Mapped[int] = mapped_column(ForeignKey("dummy_accounts.id"), nullable=False)
    
    provider_profile_ref: Mapped[str] = mapped_column(String(500), nullable=False)  # GoLogin ID, VNC endpoint
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    provider: Mapped["BrowserProvider"] = relationship(back_populates="profiles")
    dummy_account: Mapped["DummyAccount"] = relationship(back_populates="browser_profiles")
    publishing_runs: Mapped[List["PublishingRun"]] = relationship(back_populates="browser_profile")

class Campaign(Base):
    """Marketing campaign grouping assets and runs."""
    
    __tablename__ = "campaigns"
    
    __table_args__ = (
        Index("idx_campaigns_user_platform_created", "user_id", "platform_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id"), nullable=False)
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="campaigns", foreign_keys=[user_id])
    platform: Mapped["Platform"] = relationship(back_populates="campaigns")
    assets: Mapped[List["Asset"]] = relationship(back_populates="campaign")
    publishing_runs: Mapped[List["PublishingRun"]] = relationship(back_populates="campaign")


class Asset(Base):
    """Represents a media asset. Renamed from UploadedAsset."""
    
    __tablename__ = "assets"  # Was "uploaded_assets"
    
    __table_args__ = (
        Index("idx_assets_campaign_status_created", "campaign_id", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True) # Nullable for migration
    campaign_id: Mapped[Optional[int]] = mapped_column(ForeignKey("campaigns.id"), nullable=True)
    
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False) # Was original_filename
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    checksum: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="assets", foreign_keys=[user_id])
    campaign: Mapped["Campaign"] = relationship(back_populates="assets")
    post_links: Mapped[List["PublishingPostAsset"]] = relationship(back_populates="asset")


class DummyAccount(Base):
    """Automated account on a platform. Renamed from Account."""
    
    __tablename__ = "dummy_accounts" # Was "accounts"

    __table_args__ = (
        Index("idx_dummy_accounts_platform_active", "platform_id", "is_active"),
        UniqueConstraint("platform_id", "username", name="uq_dummy_accounts_platform_username"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform_id: Mapped[Optional[int]] = mapped_column(ForeignKey("platforms.id"), nullable=True)
    launch_group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("launch_groups.id"), nullable=True)
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_recurring_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    environment: Mapped[str] = mapped_column(String(50), default="prod", nullable=False)
    
    config: Mapped[Optional[dict]] = mapped_column(JSON_VARIANT, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    platform: Mapped["Platform"] = relationship(back_populates="dummy_accounts")
    launch_group: Mapped[Optional["LaunchGroup"]] = relationship(back_populates="dummy_accounts")
    persona: Mapped[Optional["DummyAccountPersona"]] = relationship(back_populates="dummy_account", uselist=False)
    browser_profiles: Mapped[List["BrowserProviderProfile"]] = relationship(back_populates="dummy_account")
    publishing_runs: Mapped[List["PublishingRun"]] = relationship(back_populates="dummy_account")
    publishing_posts: Mapped[List["PublishingPost"]] = relationship(back_populates="dummy_account")


class DummyAccountPersona(Base):
    """Tone and behavior persona for a dummy account."""
    
    __tablename__ = "dummy_account_personas"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dummy_account_id: Mapped[int] = mapped_column(ForeignKey("dummy_accounts.id"), nullable=False, unique=True)
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_label: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tone: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    archetype: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_audience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    topics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    style_guide: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    posting_goals: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    config: Mapped[Optional[dict]] = mapped_column(JSON_VARIANT, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    dummy_account: Mapped["DummyAccount"] = relationship(back_populates="persona")


class PublishingRun(Base):
    """Batch job execution metadata."""
    
    __tablename__ = "publishing_runs" # New table
    
    __table_args__ = (
        # Partial queue index
        Index("idx_runs_queue_platform_sched_priority", "platform_id", "scheduled_at", "priority", "id", 
              postgresql_where=(func.lower("status").in_(['pending', 'scheduled']))), 
        Index("idx_runs_campaign_created", "campaign_id", "created_at"),
        Index("idx_runs_dummy_created", "dummy_account_id", "created_at"),
        Index("idx_runs_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    dummy_account_id: Mapped[int] = mapped_column(ForeignKey("dummy_accounts.id"), nullable=False)
    platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id"), nullable=False)
    
    # Browser provider tracking
    browser_provider_id: Mapped[Optional[int]] = mapped_column(ForeignKey("browser_providers.id"), nullable=True)
    browser_provider_profile_id: Mapped[Optional[int]] = mapped_column(ForeignKey("browser_provider_profiles.id"), nullable=True)
    provider_session_ref: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    environment: Mapped[str] = mapped_column(String(50), default="prod", nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="publishing_runs")
    campaign: Mapped["Campaign"] = relationship(back_populates="publishing_runs")
    dummy_account: Mapped["DummyAccount"] = relationship(back_populates="publishing_runs")
    platform: Mapped["Platform"] = relationship(back_populates="publishing_runs")
    browser_provider: Mapped[Optional["BrowserProvider"]] = relationship(back_populates="publishing_runs")
    browser_profile: Mapped[Optional["BrowserProviderProfile"]] = relationship(back_populates="publishing_runs")
    posts: Mapped[List["PublishingPost"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    events: Mapped[List["PublishingRunEvent"]] = relationship(back_populates="run")


class PublishingPost(Base):
    """Single post attempt. Was PublishingRunPost."""
    
    __tablename__ = "publishing_posts" # Was "publishing_run_posts"
    
    __table_args__ = (
        Index("idx_posts_run_sequence", "publishing_run_id", "sequence_no"),
        Index("idx_posts_dummy_created_at", "dummy_account_id", "created_at"),
        Index("idx_posts_status_created_at", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    publishing_run_id: Mapped[int] = mapped_column(ForeignKey("publishing_runs.id"), nullable=False)
    dummy_account_id: Mapped[int] = mapped_column(ForeignKey("dummy_accounts.id"), nullable=False)
    platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id"), nullable=False)
    
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    external_post_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sequence_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    run: Mapped["PublishingRun"] = relationship(back_populates="posts")
    dummy_account: Mapped["DummyAccount"] = relationship(back_populates="publishing_posts")
    platform: Mapped["Platform"] = relationship(back_populates="publishing_posts")
    content: Mapped["PublishingPostContent"] = relationship(back_populates="post", uselist=False, cascade="all, delete-orphan")
    assets: Mapped[List["PublishingPostAsset"]] = relationship(back_populates="post", cascade="all, delete-orphan")
    events: Mapped[List["PublishingRunEvent"]] = relationship(back_populates="post")


class PublishingPostAsset(Base):
    """Join table for posts and assets."""
    
    __tablename__ = "publishing_post_assets"
    
    __table_args__ = (
        Index("idx_post_assets_post_position", "publishing_post_id", "position"),
        Index("idx_post_assets_asset", "asset_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    publishing_post_id: Mapped[int] = mapped_column(ForeignKey("publishing_posts.id"), nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    
    position: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_cover: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    post: Mapped["PublishingPost"] = relationship(back_populates="assets")
    asset: Mapped["Asset"] = relationship(back_populates="post_links")


class PublishingPostContent(Base):
    """Content entry for a post."""
    
    __tablename__ = "publishing_post_content" # Was "publishing_run_post_content"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    publishing_post_id: Mapped[int] = mapped_column(ForeignKey("publishing_posts.id"), nullable=False, unique=True)
    
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    tags: Mapped[Optional[dict]] = mapped_column(JSON_VARIANT, nullable=True)
    
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    tone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    extra_payload: Mapped[Optional[dict]] = mapped_column(JSON_VARIANT, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    post: Mapped["PublishingPost"] = relationship(back_populates="content")


class PublishingRunEvent(Base):
    """Audit event log."""
    
    __tablename__ = "publishing_run_events"
    
    __table_args__ = (
        Index("idx_run_events_run_created", "publishing_run_id", "created_at"),
        Index("idx_run_events_post_created", "publishing_post_id", "created_at"),
        Index("idx_run_events_type_created", "event_type", "created_at"),
        Index("idx_run_events_error_created", "error_code", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    publishing_run_id: Mapped[int] = mapped_column(ForeignKey("publishing_runs.id"), nullable=False)
    publishing_post_id: Mapped[Optional[int]] = mapped_column(ForeignKey("publishing_posts.id"), nullable=True)
    
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    old_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    worker_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    payload: Mapped[Optional[dict]] = mapped_column(JSON_VARIANT, nullable=True)
    
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    run: Mapped["PublishingRun"] = relationship(back_populates="events")
    post: Mapped["PublishingPost"] = relationship(back_populates="events")
    actor: Mapped["User"] = relationship(back_populates=None) # One way link usually sufficient
