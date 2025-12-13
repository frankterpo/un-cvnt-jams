"""Service for managing uploaded assets."""
from __future__ import annotations

from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from agent.db.models import UploadedAsset

class AssetService:
    """Service for managing uploaded assets."""

    @staticmethod
    def create_uploaded_asset(
        session: Session,
        *,
        account_id: int,
        storage_key: str,
        original_filename: str,
        mime_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
        uploaded_by_first_name: Optional[str] = None,
        uploaded_by_last_name: Optional[str] = None,
        uploaded_by_email: Optional[str] = None,
        checksum: Optional[str] = None,
        duration_ms: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        metadata_json: Optional[dict] = None,
    ) -> UploadedAsset:
        """Create a new uploaded asset record."""
        asset = UploadedAsset(
            account_id=account_id,
            storage_key=storage_key,
            original_filename=original_filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            uploaded_by_first_name=uploaded_by_first_name,
            uploaded_by_last_name=uploaded_by_last_name,
            uploaded_by_email=uploaded_by_email,
            checksum=checksum,
            duration_ms=duration_ms,
            width=width,
            height=height,
            metadata_json=metadata_json,
        )
        session.add(asset)
        session.commit()
        session.refresh(asset)
        return asset

    @staticmethod
    def list_assets_for_account(
        session: Session,
        account_id: int,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[UploadedAsset]:
        """List assets for an account, ordered by most recent upload."""
        query = select(UploadedAsset).where(
            UploadedAsset.account_id == account_id,
            UploadedAsset.deleted_at.is_(None)
        )
        
        if status:
            query = query.where(UploadedAsset.status == status)
            
        query = query.order_by(desc(UploadedAsset.uploaded_at)).limit(limit).offset(offset)
        return list(session.execute(query).scalars().all())

    @staticmethod
    def get_asset_by_id(
        session: Session,
        asset_id: int,
        account_id: int,
    ) -> Optional[UploadedAsset]:
        """Get a specific asset by ID, ensuring it belongs to the account."""
        query = select(UploadedAsset).where(
            UploadedAsset.id == asset_id,
            UploadedAsset.account_id == account_id,
            UploadedAsset.deleted_at.is_(None)
        )
        return session.execute(query).scalar_one_or_none()

    @staticmethod
    def update_asset_status(
        session: Session,
        asset_id: int,
        status: str,
    ) -> bool:
        """Update the status of an asset."""
        asset = session.get(UploadedAsset, asset_id)
        if not asset:
            return False
            
        asset.status = status
        session.commit()
        return True

    @staticmethod
    def soft_delete_asset(
        session: Session,
        asset_id: int,
        account_id: int,
    ) -> bool:
        """Soft delete an asset."""
        asset = AssetService.get_asset_by_id(session, asset_id, account_id)
        if not asset:
            return False
            
        asset.deleted_at = datetime.utcnow()
        session.commit()
        return True
