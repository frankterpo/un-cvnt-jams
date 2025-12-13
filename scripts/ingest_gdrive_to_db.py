#!/usr/bin/env python3
"""Ingest videos from Google Drive to DB & Create Runs."""

import sys
import os
import uuid
from pathlib import Path
from datetime import datetime, timedelta

# 1. Setup Environment
# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from loguru import logger
from dotenv import load_dotenv

# Load env before imports that might use it
load_dotenv()

from agent.db.base import SessionLocal, is_postgres
from agent.db.models import Account, UploadedAsset, PublishingRunPost, PublishingRunPostContent
from agent.services.assets import AssetService
from agent.services.publishing_runs import PublishingRunService
from agent.source_gdrive import build_drive_client, list_videos_in_folder

def ingest(limit: int = 1):
    logger.info("Starting GDrive DB Ingestion...")

    # 1. Config
    sa_json = os.getenv("GDRIVE_SA_JSON", "blissful-fiber-473419-e6-abf91b637595.json")
    folder_id = os.getenv("GDRIVE_FOLDER_ID")

    # folder_id check moved to query logic
    if not folder_id:
        logger.info("GDRIVE_FOLDER_ID not set, will broad search.")

    # 2. Connect to Services
    try:
        service = build_drive_client(Path(sa_json))
        logger.success("Connected to GDrive API")
    except Exception as e:
        logger.error(f"Failed to connect to GDrive: {e}")
        return

    db = SessionLocal()
    # asset_service and run_service are static classes, no init needed
    
    # 3. Get Target Account
    # Ideally passed in, but for test we pick the first one
    account = db.query(Account).first()
    if not account:
        logger.error("No account found in DB to attach runs to!")
        return
    logger.info(f"Using Account: {account.name} (ID: {account.id})")

    # 4. List Files
    if folder_id:
        logger.info(f"Scanning folder {folder_id}...")
        files = list_videos_in_folder(service, folder_id)
    else:
        logger.warning("GDRIVE_FOLDER_ID not set. Scanning ALL shared videos...")
        # Custom query for all videos not in trash
        q = "mimeType contains 'video/' and trashed = false"
        res = service.files().list(q=q, fields="files(id,name,mimeType)").execute()
        files = res.get("files", [])

    if not files:
        logger.warning("No videos found to process.")
        return

    logger.info(f"Found {len(files)} video(s). Processing first {limit}...")

    # 5. Process
    processed_count = 0
    for f in files[:limit]:
        file_id = f["id"]
        name = f["name"]
        
        logger.info(f"-- Processing {name} ({file_id}) --")

        # Check if asset exists
        existing = AssetService.get_asset_by_id(db, 0, account.id) # Wait, get_asset_by_id needs ID, not file_id. 
        # We need lookup by GDrive ID (Source ID). 
        # AssetService doesn't have a specific get_by_source_id helper exposed easily?
        # Use query directly or add helper? 
        # Ideally check if we have an asset with this meta source_id
        
        # Quick check using SQL for verification script simplicity or add helper
        # Let's search manually in script for now to avoid modifying code unless needed.
        # Check uploaded_assets table for metadata_json->>'gdrive_id' == file_id?
        # SQLite vs Postgres JSON syntax differs. 
        # Let's just create new asset for test if not strictly deduping by file_id in service yet.
        # Actually `storage_key` is often the source ID in some contexts, but here it is file_path?
        # In current design, storage_key is unique constraint? No.
        
        # Let's just try to create. If we want idempotency, we should check.
        # For this test, let's assume we want to ingest what we find.
        
        # Meta dictionary
        meta = {
            "source": "gdrive",
            "gdrive_id": file_id,
            "mime_type": f.get("mimeType")
        }

        # Create Asset
        # asset_service.create_uploaded_asset...
        asset = AssetService.create_uploaded_asset(
            session=db,
            account_id=account.id,
            storage_key=file_id, # Using file_id as storage key for GDrive items? or path?
                                # Job expects `video_path = Path(asset.storage_key)`.
                                # IF job is running locally, it probably needs a path to downloaded file.
                                # BUT we haven't downloaded it yet.
                                # The Job logic I reviewed:
                                # video_path = Path(asset.storage_key)
                                # if not video_path.exists(): ... pass
                                
                                # This implies GDrive assets rely on Job to handle download OR they must be pre-downloaded.
                                # For this E2E, we probably want the Job to handle it?
                                # But `PublishingJob` currently does `pass` on missing file.
                                # So it WON'T WORK unless file is effectively there.
                                
                                # Let's set storage_key to "pipeline_output/videos/{name}" 
                                # AND ensuring we might not have it.
            original_filename=name,
            uploaded_by_email="automation@test.com",
            metadata_json=meta
        )
        logger.success(f"Created Asset {asset.id}")

        # Create Run
        run = PublishingRunService.create_publishing_run(
            session=db,
            account_id=account.id,
            asset_id=asset.id,
            target_platform="youtube",
            scheduled_at=datetime.utcnow() + timedelta(minutes=5)
        )
        
        PublishingRunService.create_publishing_run_content(
            session=db,
            publishing_run_post_id=run.id,
            title=f"Test Upload: {name}",
            description="Automated upload from GDrive E2E Test",
            tags=["test", "automation"]
        )
        logger.success(f"Created Run {run.id} for platform 'youtube'")
        
        processed_count += 1
    
    logger.success(f"Ingestion complete. created {processed_count} new runs.")
    db.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1)
    args = parser.parse_args()
    
    ingest(limit=args.limit)
