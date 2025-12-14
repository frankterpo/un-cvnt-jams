"""Browser Provider Allocator Service.

Responsible for selecting appropriate browser provider and profile
for a given dummy_account before creating a publishing_run.
"""
from __future__ import annotations

from typing import Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from agent.db.models import (
    BrowserProvider,
    BrowserProviderProfile,
    DummyAccount
)


class BrowserProviderAllocator:
    """Allocates browser providers and profiles for publishing runs."""
    
    # Provider priority order (first = preferred)
    PROVIDER_PRIORITY = ['GOLOGIN', 'NOVNC']
    
    @staticmethod
    def allocate(
        session: Session,
        dummy_account_id: int,
    ) -> Tuple[Optional[int], Optional[int], Optional[str]]:
        """
        Allocate a browser provider profile for the given dummy account.
        
        Returns:
            Tuple of (browser_provider_id, browser_provider_profile_id, provider_profile_ref)
            Returns (None, None, None) if no suitable profile found.
        """
        # Get all active profiles for this dummy account
        query = (
            select(BrowserProviderProfile)
            .join(BrowserProvider)
            .where(
                and_(
                    BrowserProviderProfile.dummy_account_id == dummy_account_id,
                    BrowserProviderProfile.status == 'active',
                    BrowserProvider.is_active == True
                )
            )
            .order_by(
                # Prefer default profiles
                BrowserProviderProfile.is_default.desc(),
                # Then most recently used (for session reuse)
                BrowserProviderProfile.last_used_at.desc().nulls_last()
            )
        )
        
        profiles = list(session.execute(query).scalars().all())
        
        if not profiles:
            return None, None, None
        
        # Group by provider code for priority selection
        profiles_by_provider = {}
        for profile in profiles:
            code = profile.provider.code
            if code not in profiles_by_provider:
                profiles_by_provider[code] = []
            profiles_by_provider[code].append(profile)
        
        # Select based on priority
        for provider_code in BrowserProviderAllocator.PROVIDER_PRIORITY:
            if provider_code in profiles_by_provider:
                # Check if provider is within quota (stub for now)
                if BrowserProviderAllocator._is_provider_available(session, provider_code):
                    selected = profiles_by_provider[provider_code][0]
                    
                    # Update last_used_at
                    selected.last_used_at = datetime.utcnow()
                    session.commit()
                    
                    return (
                        selected.browser_provider_id,
                        selected.id,
                        selected.provider_profile_ref
                    )
        
        # Fallback: use any available profile
        selected = profiles[0]
        selected.last_used_at = datetime.utcnow()
        session.commit()
        
        return (
            selected.browser_provider_id,
            selected.id,
            selected.provider_profile_ref
        )
    
    @staticmethod
    def _is_provider_available(session: Session, provider_code: str) -> bool:
        """
        Check if provider is available (not over quota).
        
        TODO: Implement actual quota checking against monthly usage.
        For now, returns True (always available) unless explicitly disabled.
        """
        provider = session.execute(
            select(BrowserProvider).where(BrowserProvider.code == provider_code)
        ).scalar_one_or_none()
        
        if not provider or not provider.is_active:
            return False
        
        # Stub: Always return True for now
        # Future: Compare get_monthly_usage(provider.id) vs provider.max_launches_per_month
        return True
    
    @staticmethod
    def get_provider_by_code(session: Session, code: str) -> Optional[BrowserProvider]:
        """Get a browser provider by its code."""
        return session.execute(
            select(BrowserProvider).where(BrowserProvider.code == code)
        ).scalar_one_or_none()
    
    @staticmethod
    def get_fallback_profile(
        session: Session,
        dummy_account_id: int,
        exclude_provider_code: str,
    ) -> Tuple[Optional[int], Optional[int], Optional[str], Optional[str]]:
        """
        Get a fallback profile excluding the specified provider.
        
        Returns:
            Tuple of (browser_provider_id, browser_provider_profile_id, provider_profile_ref, provider_code)
        """
        # Get all active profiles except the excluded provider
        query = (
            select(BrowserProviderProfile)
            .join(BrowserProvider)
            .where(
                and_(
                    BrowserProviderProfile.dummy_account_id == dummy_account_id,
                    BrowserProviderProfile.status == 'active',
                    BrowserProvider.is_active == True,
                    BrowserProvider.code != exclude_provider_code
                )
            )
            .order_by(
                BrowserProviderProfile.is_default.desc(),
                BrowserProviderProfile.last_used_at.desc().nulls_last()
            )
        )
        
        profiles = list(session.execute(query).scalars().all())
        
        if not profiles:
            return None, None, None, None
        
        selected = profiles[0]
        selected.last_used_at = datetime.utcnow()
        session.commit()
        
        return (
            selected.browser_provider_id,
            selected.id,
            selected.provider_profile_ref,
            selected.provider.code
        )
    
    @staticmethod
    def mark_provider_exhausted(
        session: Session,
        profile_id: int,
        reason: str = "api_limit"
    ) -> None:
        """Mark a provider profile as exhausted (temporarily unavailable)."""
        profile = session.get(BrowserProviderProfile, profile_id)
        if profile:
            profile.status = 'exhausted'
            session.commit()
    
    @staticmethod
    def create_profile(
        session: Session,
        *,
        browser_provider_id: int,
        dummy_account_id: int,
        provider_profile_ref: str,
        is_default: bool = False,
    ) -> BrowserProviderProfile:
        """Create a new browser provider profile mapping."""
        profile = BrowserProviderProfile(
            browser_provider_id=browser_provider_id,
            dummy_account_id=dummy_account_id,
            provider_profile_ref=provider_profile_ref,
            is_default=is_default,
            status='active'
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)
        return profile
