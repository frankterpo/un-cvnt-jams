#!/usr/bin/env python3
"""Verify DB layer functionality."""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent.db.base import SessionLocal
from agent.services.assets import AssetService
from agent.services.publishing_runs import PublishingRunService
from agent.db.models import Account

def verify():
    session = SessionLocal()
    try:
        print("1. Verifying Accounts...")
        # Should have at least the migrated account 'accounts' (from the previous step's output)
        account = session.query(Account).first()
        if not account:
            print("   -> No account found. Creating test account.")
            account = Account(name="Test Account")
            session.add(account)
            session.commit()
            session.refresh(account)
        print(f"   -> Using account: {account.name} (ID: {account.id})")

        print("\n2. Testing Asset Creation...")
        asset = AssetService.create_uploaded_asset(
            session,
            account_id=account.id,
            storage_key="/tmp/test_video.mp4",
            original_filename="test_video.mp4",
            uploaded_by_email="tester@example.com"
        )
        print(f"   -> Created asset ID: {asset.id}")

        print("\n3. Testing Publishing Run Creation...")
        run = PublishingRunService.create_publishing_run(
            session,
            account_id=account.id,
            asset_id=asset.id,
            target_platform="YOUTUBE",
            scheduled_at=datetime.utcnow() + timedelta(hours=1)
        )
        print(f"   -> Created run ID: {run.id} (Status: {run.status})")

        print("\n4. Testing Content Creation...")
        content = PublishingRunService.create_publishing_run_content(
            session,
            publishing_run_post_id=run.id,
            title="Test Video",
            description="This is a test description"
        )
        print(f"   -> Created content for run {run.id}")

        print("\n5. Verifying Data Retrieval...")
        pending_runs = PublishingRunService.get_pending_runs(session)
        print(f"   -> Found {len(pending_runs)} pending runs.")
        
        found = any(r.id == run.id for r in pending_runs)
        if found:
            print("   -> SUCCESS: Created run was found in pending list.")
        else:
            print("   -> FAILURE: Created run not found in pending list.")

        print("\n6. Cleaning up...")
        # Optional: delete test data
        # session.delete(run) # cascades to content
        # session.delete(asset)
        # session.commit()
        print("   -> Test complete.")

    except Exception as e:
        print(f"VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    verify()
