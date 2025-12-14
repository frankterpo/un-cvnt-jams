"""Service for managing publishing runs."""
from __future__ import annotations

from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, desc, or_, func

# Updated imports for new schema
from agent.db.models import PublishingPost, PublishingPostContent, PublishingRun, Platform, PublishingPostAsset
from agent.services.browser_provider_allocator import BrowserProviderAllocator

class PublishingRunService:
    """Service for managing publishing runs (Modernized)."""

    @staticmethod
    def _get_platform_id(session: Session, code: str) -> int:
        platform = session.execute(select(Platform).where(Platform.code == code)).scalar_one_or_none()
        if not platform:
            # Fallback for now or raise error? Assuming existing platforms
            if code == "instagram": return 1
            if code == "tiktok": return 2
            if code == "youtube": return 3
            return 1
        return platform.id

    @staticmethod
    def create_publishing_run(
        session: Session,
        *,
        account_id: int, # This is dummy_account_id
        asset_id: int,
        target_platform: str,
        scheduled_at: Optional[datetime] = None,
        priority: int = 0,
        created_by_user_id: Optional[int] = None,
        campaign_id: int = 1, # Default to legacy campaign
    ) -> PublishingPost:
        """Create a new publishing run (Post wrapped in Run)."""
        
        platform_id = PublishingRunService._get_platform_id(session, target_platform.lower())
        user_id = created_by_user_id or 1 # Default admin
        
        # Allocate browser provider
        # Allocate browser provider (Static selection)
        # We just pick the first active profile for the account.
        from agent.db.models import BrowserProvider, BrowserProviderProfile
        profile = session.execute(
            select(BrowserProviderProfile)
            .join(BrowserProvider)
            .where(
                BrowserProviderProfile.dummy_account_id == account_id,
                BrowserProviderProfile.status == 'active',
                BrowserProvider.is_active == True
            )
            .limit(1)
        ).scalar_one_or_none()
        
        provider_id = profile.browser_provider_id if profile else None
        profile_id = profile.id if profile else None
        profile_ref = None

        # Create parent Run with provider info
        run = PublishingRun(
            user_id=user_id,
            campaign_id=campaign_id,
            dummy_account_id=account_id,
            platform_id=platform_id,
            browser_provider_id=provider_id,
            browser_provider_profile_id=profile_id,
            provider_session_ref=None,  # Set at execution time
            status="SCHEDULED" if scheduled_at else "PENDING",
            scheduled_at=scheduled_at,
            priority=priority,
            environment="prod"
        )
        session.add(run)
        session.flush() # Get ID

        # Create Post
        post = PublishingPost(
            publishing_run_id=run.id,
            dummy_account_id=account_id,
            platform_id=platform_id,
            status="SCHEDULED" if scheduled_at else "PENDING",
            scheduled_at=scheduled_at,
            sequence_no=1
        )
        session.add(post)
        session.flush()

        # Link Asset
        post_asset = PublishingPostAsset(
            publishing_post_id=post.id,
            asset_id=asset_id,
            position=1,
            is_cover=False
        )
        session.add(post_asset)

        session.commit()
        session.refresh(post)
        return post

    @staticmethod
    def create_publishing_run_content(
        session: Session,
        *,
        publishing_run_post_id: int, # This is post_id
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        language: Optional[str] = None,
        extra_payload_json: Optional[dict] = None,
    ) -> PublishingPostContent:
        """Create content metadata for a publishing post."""
        content = PublishingPostContent(
            publishing_post_id=publishing_run_post_id,
            title=title,
            description=description,
            tags={"items": tags} if tags else None, # JSON expectation
            language=language,
            extra_payload=extra_payload_json,
        )
        session.add(content)
        session.commit()
        session.refresh(content)
        return content

    @staticmethod
    def get_pending_runs(
        session: Session,
        limit: int = 10,
    ) -> List[PublishingPost]:
        """
        Get pending publishing posts that are ready to run.
        """
        # Note: We return Posts, not Runs, because Job executes Posts.
        query = select(PublishingPost).where(
            or_(
                PublishingPost.status == "PENDING",
                (PublishingPost.status == "SCHEDULED") & (PublishingPost.scheduled_at <= func.now())
            )
        ).order_by(
            # Join with run probably for priority? Or assume post doesn't have priority?
            # Creating separate priority on Post might be good, or inherit from Run.
            # Schema has priority on Run.
            # We can join.
            # For simplicity, order by scheduled_at and ID.
            PublishingPost.scheduled_at.asc(),
            PublishingPost.id.asc()
        ).limit(limit)
        
        # We might want to eager load dependencies
        # query = query.options(joinedload(PublishingPost.assets), joinedload(PublishingPost.content))
        
        return list(session.execute(query).scalars().all())

    @staticmethod
    def get_runs_for_account(
        session: Session,
        account_id: int,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[PublishingPost]:
        """Get publishing posts for an account."""
        query = select(PublishingPost).where(
            PublishingPost.dummy_account_id == account_id
        )
        
        if status:
            query = query.where(PublishingPost.status == status)
            
        query = query.order_by(desc(PublishingPost.id)).limit(limit)
        return list(session.execute(query).scalars().all())

    @staticmethod
    def update_run_status(
        session: Session,
        run_id: int, # post_id
        status: str,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update the status of a publishing post (and parent run if needed)."""
        post = session.get(PublishingPost, run_id)
        if not post:
            return False
            
        post.status = status
        
        if status == "RUNNING":
            post.started_at = datetime.utcnow()
        elif status in ("SUCCESS", "FAILED", "CANCELLED", "SKIPPED"):
            post.completed_at = datetime.utcnow()
        
        if status == "FAILED":
            # post doesn't have retry_count in schema? Schema check: Post does not, Run does.
            # Logic: Update parent run retry count?
            if post.run:
                post.run.retry_count += 1
                
            if error_message:
                post.error_message = error_message
        elif error_message:
            post.error_message = error_message
            
        # Update parent Run status?
        # If execution is 1:1, yes.
        if post.run:
            if status == "RUNNING" and post.run.status != "RUNNING":
                 post.run.status = "RUNNING"
                 post.run.started_at = datetime.utcnow()
            elif status in ("SUCCESS", "SKIPPED") and post.run.status not in ("SUCCESS", "FAILED"):
                 post.run.status = status
                 post.run.completed_at = datetime.utcnow()
            elif status == "FAILED":
                 post.run.status = "FAILED"
                 post.run.error_message = error_message
            
        session.commit()
        return True
