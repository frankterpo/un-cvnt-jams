"""Service for managing publishing runs."""
from __future__ import annotations

from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, desc, or_, func

from agent.db.models import PublishingRunPost, PublishingRunPostContent

class PublishingRunService:
    """Service for managing publishing runs."""

    @staticmethod
    def create_publishing_run(
        session: Session,
        *,
        account_id: int,
        asset_id: int,
        target_platform: str,
        scheduled_at: Optional[datetime] = None,
        priority: int = 0,
        created_by_user_id: Optional[int] = None,
    ) -> PublishingRunPost:
        """Create a new publishing run."""
        run = PublishingRunPost(
            account_id=account_id,
            asset_id=asset_id,
            target_platform=target_platform,
            scheduled_at=scheduled_at,
            priority=priority,
            created_by_user_id=created_by_user_id,
            status="SCHEDULED" if scheduled_at else "PENDING",
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return run

    @staticmethod
    def create_publishing_run_content(
        session: Session,
        *,
        publishing_run_post_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        language: Optional[str] = None,
        extra_payload_json: Optional[dict] = None,
    ) -> PublishingRunPostContent:
        """Create content metadata for a publishing run."""
        content = PublishingRunPostContent(
            publishing_run_post_id=publishing_run_post_id,
            title=title,
            description=description,
            tags=tags,
            language=language,
            extra_payload_json=extra_payload_json,
        )
        session.add(content)
        session.commit()
        session.refresh(content)
        return content

    @staticmethod
    def get_pending_runs(
        session: Session,
        limit: int = 10,
    ) -> List[PublishingRunPost]:
        """
        Get pending publishing runs that are ready to run.
        
        Includes runs that are PENDING or SCHEDULED where scheduled_at <= now.
        Orders by priority DESC, scheduled_at ASC, created_at ASC.
        """
        # Use DB server time for comparison to avoid timezone mismatch
        query = select(PublishingRunPost).where(
            or_(
                PublishingRunPost.status == "PENDING",
                (PublishingRunPost.status == "SCHEDULED") & (PublishingRunPost.scheduled_at <= func.now())
            )
        ).order_by(
            desc(PublishingRunPost.priority),
            PublishingRunPost.scheduled_at.asc(),
            PublishingRunPost.id.asc() # fallback stable sort
        ).limit(limit)
        
        return list(session.execute(query).scalars().all())

    @staticmethod
    def get_runs_for_account(
        session: Session,
        account_id: int,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[PublishingRunPost]:
        """Get publishing runs for an account."""
        query = select(PublishingRunPost).where(
            PublishingRunPost.account_id == account_id
        )
        
        if status:
            query = query.where(PublishingRunPost.status == status)
            
        query = query.order_by(desc(PublishingRunPost.id)).limit(limit)
        return list(session.execute(query).scalars().all())

    @staticmethod
    def update_run_status(
        session: Session,
        run_id: int,
        status: str,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update the status of a publishing run."""
        run = session.get(PublishingRunPost, run_id)
        if not run:
            return False
            
        run.status = status
        
        if status == "RUNNING":
            run.started_at = datetime.utcnow()
        elif status in ("SUCCESS", "FAILED", "CANCELLED", "SKIPPED"):
            run.completed_at = datetime.utcnow()
        
        if status == "FAILED":
            run.retry_count += 1
            if error_message:
                run.error_message = error_message
        elif error_message:
            # Also save error message if provided for other statuses (e.g. warning)
            run.error_message = error_message
            
        session.commit()
        return True
