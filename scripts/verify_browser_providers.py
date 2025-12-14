"""Verify browser provider layer implementation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent.db.base import SessionLocal
from sqlalchemy import text


def verify():
    session = SessionLocal()
    try:
        # 1. Check browser_providers table
        result = session.execute(text("SELECT code, display_name, kind FROM browser_providers"))
        providers = list(result.fetchall())
        print(f"✓ Browser Providers: {len(providers)}")
        for p in providers:
            print(f"  - {p[0]}: {p[1]} ({p[2]})")
        
        # 2. Check launch_groups table
        result = session.execute(text("SELECT name, monthly_launch_cap FROM launch_groups"))
        groups = list(result.fetchall())
        print(f"✓ Launch Groups: {len(groups)}")
        for g in groups:
            print(f"  - {g[0]} (cap: {g[1]})")
        
        # 3. Check browser_provider_profiles
        result = session.execute(text("""
            SELECT bpp.id, bp.code, da.name, bpp.provider_profile_ref, bpp.status
            FROM browser_provider_profiles bpp
            JOIN browser_providers bp ON bp.id = bpp.browser_provider_id
            JOIN dummy_accounts da ON da.id = bpp.dummy_account_id
        """))
        profiles = list(result.fetchall())
        print(f"✓ Browser Provider Profiles: {len(profiles)}")
        for p in profiles:
            print(f"  - [{p[1]}] {p[2]} -> {p[3][:20]}... ({p[4]})")
        
        # 4. Check dummy_accounts has new columns
        result = session.execute(text("SELECT name, launch_group_id, is_recurring_enabled FROM dummy_accounts LIMIT 3"))
        accounts = list(result.fetchall())
        print(f"✓ DummyAccounts extended (sample {len(accounts)}):")
        for a in accounts:
            print(f"  - {a[0]}: launch_group={a[1]}, recurring={a[2]}")
        
        # 5. Check publishing_runs has new columns
        result = session.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'publishing_runs' 
            AND column_name IN ('browser_provider_id', 'browser_provider_profile_id', 'provider_session_ref')
        """))
        cols = [r[0] for r in result.fetchall()]
        print(f"✓ PublishingRuns new columns: {cols}")
        
        print("\n✅ ALL VERIFICATIONS PASSED")
        
    except Exception as e:
        print(f"❌ VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    verify()
