import sys
from pathlib import Path
from datetime import datetime, timezone

# Add src manually because -I flag ignores PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from agent.db.base import SessionLocal
from agent.services.publishing_runs import PublishingRunService
from agent.db.models import Asset, DummyAccount

def queue_test_job():
    session = SessionLocal()
    try:
        # 1. Ensure Asset Exists
        # Use relative path compatible with EC2 or Local
        base_dir = Path(__file__).resolve().parent.parent
        video_path = base_dir / "sample_videos" / "test_tiktok.mp4"
        
        if not video_path.exists():
            print(f"Error: Video not found at {video_path}")
            return

        # Check if asset exists or create
        # We store the absolute path as the key, but for portability let's use the filename or relative path in DB if new?
        # Creating new asset with current path to ensure worker finds it (if worker uses this path).
        # Note: Worker needs to access this file. On EC2 it will be at /home/ec2-user/un-cvnt-jams/...
        # So using `video_path` (which resolves to absolute path on the machine running this script) is correct
        # IF we run this script ON EC2.
        
        asset = session.query(Asset).filter_by(storage_key=str(video_path)).first()
        if not asset:
            print("Creating new Asset record...")
            asset = Asset(
                storage_key=str(video_path),
                original_name="test_tiktok.mp4",
                status="ready",
                user_id=1, 
                campaign_id=1 
            )
            session.add(asset)
            session.commit()
            session.refresh(asset)
        
        print(f"Using Asset ID: {asset.id}")

        # 2. Get Account ID
        account_name = "viixenviices"
        account = session.query(DummyAccount).filter(DummyAccount.name.ilike(f"%{account_name}%")).first()
        
        if not account:
            print(f"Account '{account_name}' not found. Creating...")
            account = DummyAccount(
                name=account_name,
                username="franciscoterpolilli+viixenviices@gmail.com", 
                platform_id=1, 
                is_active=True,
                launch_group_id=1 # Default group
            )
            session.add(account)
            session.commit()
            session.refresh(account)
            
        print(f"Using Account ID: {account.id} ({account.name})")

        # 3. Queue Jobs (IG + TikTok)
        platforms = ["instagram", "tiktok"]
        
        for platform in platforms:
            print(f"Queuing {platform} Post...")
            post = PublishingRunService.create_publishing_run(
                session,
                account_id=account.id,
                asset_id=asset.id,
                target_platform=platform,
                scheduled_at=datetime.now(timezone.utc),
                priority=10
            )
            
            PublishingRunService.create_publishing_run_content(
                session,
                publishing_run_post_id=post.id,
                description=f"Test upload via EC2 Worker 🚀 #{platform}",
                title=f"Test Upload {platform}"
            )
            print(f" -> Queued {platform.upper()}: Job ID {post.id} (Run {post.publishing_run_id})")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    queue_test_job()
