import sys
from pathlib import Path
from datetime import datetime

# Add src manually because -I flag ignores PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from agent.db.base import SessionLocal
from agent.services.publishing_runs import PublishingRunService
from agent.db.models import Asset

def queue_test_job():
    session = SessionLocal()
    try:
        # 1. Ensure Asset Exists
        # Use absolute path to sample video
        video_path = Path("/Users/franciscoterpolilli/Projects/un-cvnt-jams/sample_videos/test_tiktok.mp4")
        if not video_path.exists():
            print(f"Error: Video not found at {video_path}")
            return

        # Check if asset exists or create
        asset = session.query(Asset).filter_by(storage_key=str(video_path)).first()
        if not asset:
            print("Creating new Asset record...")
            asset = Asset(
                storage_key=str(video_path),
                original_name="test_tiktok.mp4",
                status="ready",
                user_id=1, # Admin
                campaign_id=1 # Legacy
            )
            session.add(asset)
            session.commit()
            session.refresh(asset)
        
        print(f"Using Asset ID: {asset.id}")

        # 2. Get Account ID
        # We need the dummy_account_id for 'viixenviices'
        from agent.db.models import DummyAccount
        # We know mapping: viixenviices is likely mapped to an account or we find by name/username
        # Let's search by name
        # .env: GOLOGIN_PROFILE_VIIXENVIICES -> 693d...
        # In DB, do we have an account named 'viixenviices'?
        # The migration renamed 'accounts' -> 'dummy_accounts'. 
        # Existing data from seed_legacy wasn't applied to RDS (DB was empty before migration? No, existing schema but maybe empty data).
        # We might need to create the dummy account if it doesn't exist.
        
        account_name = "viixenviices"
        account = session.query(DummyAccount).filter(DummyAccount.name.ilike(f"%{account_name}%")).first()
        
        if not account:
            print(f"Account '{account_name}' not found. Creating...")
            # Create dummy account
            account = DummyAccount(
                name=account_name,
                username="frankpablote@gmail.com", # Matching env config logic
                platform_id=1, # Instagram
                is_active=True
            )
            session.add(account)
            session.commit()
            session.refresh(account)
            
        print(f"Using Account ID: {account.id} ({account.name})")

        # 3. Queue Job
        print("Queuing Publishing Post...")
        post = PublishingRunService.create_publishing_run(
            session,
            account_id=account.id,
            asset_id=asset.id,
            target_platform="instagram",
            scheduled_at=datetime.utcnow(),
            priority=10
        )
        
        # Add content
        PublishingRunService.create_publishing_run_content(
            session,
            publishing_run_post_id=post.id,
            description="Test upload via GoLogin automation 🚀 #test #automation",
            title="Test Upload"
        )
        
        print(f"queued Job ID: {post.id} (Run ID: {post.publishing_run_id})")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    queue_test_job()
