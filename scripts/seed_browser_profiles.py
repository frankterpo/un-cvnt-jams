"""Seed browser provider profiles from existing GoLogin configuration.

This script migrates GoLogin profile IDs from .env into browser_provider_profiles.
"""
import sys
from pathlib import Path
import os

# Add src to path FIRST (before any project imports)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from agent.db.base import SessionLocal
from agent.db.models import BrowserProvider, BrowserProviderProfile, DummyAccount
from agent.services.browser_provider_allocator import BrowserProviderAllocator
from sqlalchemy import select


# GoLogin profile mappings from .env
GOLOGIN_PROFILES = {
    'viixenviices': os.getenv('GOLOGIN_PROFILE_VIIXENVIICES'),
    'popmessparis': os.getenv('GOLOGIN_PROFILE_POPMESSPARIS'),
    'halohavok': os.getenv('GOLOGIN_PROFILE_HALOHAVOK'),
    'cigsntofu': os.getenv('GOLOGIN_PROFILE_CIGSNTOFU'),
    'lavenderliqour': os.getenv('GOLOGIN_PROFILE_LAVENDERLIQOUR'),
    'hotcaviarx': os.getenv('GOLOGIN_PROFILE_HOTCAVIARX'),
}


def seed_profiles():
    session = SessionLocal()
    try:
        # Get GoLogin provider
        gologin = session.execute(
            select(BrowserProvider).where(BrowserProvider.code == 'GOLOGIN')
        ).scalar_one_or_none()
        
        if not gologin:
            print("ERROR: GoLogin provider not found. Run migration first.")
            return
        
        print(f"Found GoLogin provider (ID: {gologin.id})")
        
        created = 0
        skipped = 0
        
        for account_name, profile_id in GOLOGIN_PROFILES.items():
            if not profile_id:
                print(f"SKIP: No profile ID for {account_name}")
                skipped += 1
                continue
            
            # Find dummy account by name
            account = session.execute(
                select(DummyAccount).where(DummyAccount.name.ilike(f"%{account_name}%"))
            ).scalar_one_or_none()
            
            if not account:
                # Create dummy account if it doesn't exist
                print(f"Creating dummy account: {account_name}")
                account = DummyAccount(
                    name=account_name,
                    username=account_name,
                    platform_id=1,  # Instagram
                    is_active=True
                )
                session.add(account)
                session.flush()
            
            # Check if profile already exists
            existing = session.execute(
                select(BrowserProviderProfile).where(
                    BrowserProviderProfile.browser_provider_id == gologin.id,
                    BrowserProviderProfile.provider_profile_ref == profile_id
                )
            ).scalar_one_or_none()
            
            if existing:
                print(f"SKIP: Profile already exists for {account_name} ({profile_id})")
                skipped += 1
                continue
            
            # Create browser provider profile
            profile = BrowserProviderProfile(
                browser_provider_id=gologin.id,
                dummy_account_id=account.id,
                provider_profile_ref=profile_id,
                status='active',
                is_default=True
            )
            session.add(profile)
            print(f"CREATED: {account_name} -> {profile_id}")
            created += 1
        
        session.commit()
        print(f"\nDone: {created} created, {skipped} skipped")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    seed_profiles()
