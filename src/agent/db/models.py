"""ORM models for the social agent."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    DateTime,
    func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent.db.base import Base


class Account(Base):
    """Represents a client or social media identity."""
    
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    primary_contact_email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)

    # Relationships
    uploaded_assets: Mapped[List["UploadedAsset"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    publishing_runs: Mapped[List["PublishingRunPost"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class UploadedAsset(Base):
    """Represents a raw file uploaded/ingested into the system."""
    
    __tablename__ = "uploaded_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    
    uploaded_by_first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    uploaded_by_last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    uploaded_by_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    status: Mapped[str] = mapped_column(String(50), default="PENDING_PROCESSING", nullable=False)
    checksum: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    account: Mapped["Account"] = relationship(back_populates="uploaded_assets")
    publishing_runs: Mapped[List["PublishingRunPost"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )


class PublishingRunPost(Base):
    """Represents a single post attempt to a specific platform."""
    
    __tablename__ = "publishing_run_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("uploaded_assets.id"), nullable=False)
    
    target_platform: Mapped[str] = mapped_column(String(50), nullable=False)  # YOUTUBE, TIKTOK, INSTAGRAM
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    account: Mapped["Account"] = relationship(back_populates="publishing_runs")
    asset: Mapped["UploadedAsset"] = relationship(back_populates="publishing_runs")
    content: Mapped["PublishingRunPostContent"] = relationship(
        back_populates="publishing_run_post", uselist=False, cascade="all, delete-orphan"
    )


class PublishingRunPostContent(Base):
    """Content metadata for a specific post (title, description, tags, etc)."""
    
    __tablename__ = "publishing_run_post_content"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    publishing_run_post_id: Mapped[int] = mapped_column(
        ForeignKey("publishing_run_posts.id"), nullable=False, unique=True
    )
    
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    extra_payload_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    publishing_run_post: Mapped["PublishingRunPost"] = relationship(back_populates="content")
