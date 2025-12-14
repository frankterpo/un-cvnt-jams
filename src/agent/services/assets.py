"""Service for managing uploaded assets."""
from __future__ import annotations

from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from agent.db.models import Asset

class AssetService:
    """Service for managing assets (Modernized for Schema v2)."""

    @staticmethod
    def create_asset(
        session: Session,
        *,
        user_id: int,
        campaign_id: Optional[int] = None,
        storage_key: str,
        original_name: str,
        mime_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
        checksum: Optional[str] = None,
        duration_ms: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> Asset:
        """Create a new asset record."""
        asset = Asset(
            user_id=user_id,
            campaign_id=campaign_id,
            storage_key=storage_key,
            original_name=original_name,
            mime_type=mime_type,
            size_bytes=size_bytes,
            checksum=checksum,
            duration_ms=duration_ms,
            width=width,
            height=height,
            status="pending"
        )
        session.add(asset)
        session.commit()
        session.refresh(asset)
        return asset

    @staticmethod
    def list_assets_for_campaign(
        session: Session,
        campaign_id: int,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Asset]:
        """List assets for a campaign, ordered by most recent upload."""
        query = select(Asset).where(
            Asset.campaign_id == campaign_id,
            Asset.deleted_at.is_(None)
        )
        
        if status:
            query = query.where(Asset.status == status)
            
        query = query.order_by(desc(Asset.uploaded_at)).limit(limit).offset(offset)
        return list(session.execute(query).scalars().all())

    @staticmethod
    def get_asset_by_id(
        session: Session,
        asset_id: int,
    ) -> Optional[Asset]:
        """Get a specific asset by ID."""
        return session.get(Asset, asset_id)

    @staticmethod
    def update_asset_status(
        session: Session,
        asset_id: int,
        status: str,
    ) -> bool:
        """Update the status of an asset."""
        asset = session.get(Asset, asset_id)
        if not asset:
            return False
            
        asset.status = status
        session.commit()
        return True

    @staticmethod
    def soft_delete_asset(
        session: Session,
        asset_id: int,
        deleted_by_user_id: Optional[int] = None,
    ) -> bool:
        """Soft delete an asset."""
        asset = session.get(Asset, asset_id)
        if not asset:
            return False
            
        asset.deleted_at = datetime.utcnow()
        asset.deleted_by_user_id = deleted_by_user_id
        session.commit()
        return True
