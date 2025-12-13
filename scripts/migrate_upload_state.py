#!/usr/bin/env python3
"""Migrate upload state from JSON to SQLite."""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent.db.base import SessionLocal
from agent.db.models import Account, UploadedAsset, PublishingRunPost, PublishingRunPostContent
from agent.services.assets import AssetService
from agent.services.publishing_runs import PublishingRunService

def main():
    parser = argparse.ArgumentParser(description="Migrate upload_state.json to DB")
    parser.add_argument("--dry-run", action="store_true", help="Do not commit changes")
    args = parser.parse_args()

    state_path = Path("pipeline_output/upload_state.json")
    if not state_path.exists():
        print(f"No state file found at {state_path}. Skipping.")
        return

    session = SessionLocal()
    try:
        # Ensure we have an account to link to.
        # We will link to the first account found, or create a 'Legacy/Default' one.
        account = session.query(Account).first()
        if not account:
            if args.dry_run:
                print("[DRY RUN] No account found. Would create 'Migrated Account'.")
                return # Can't proceed in dry run without account ID logic mock
            
            print("No account found. Creating 'Migrated Account'.")
            account = Account(name="Migrated Account")
            session.add(account)
            session.commit()
            session.refresh(account)
        
        print(f"Linking migrated assets to Account: {account.name} (ID: {account.id})")

        with open(state_path, "r") as f:
            records = json.load(f)

        # Group by drive_file_id
        grouped = {}
        for r in records:
            fid = r["drive_file_id"]
            if fid not in grouped:
                grouped[fid] = []
            grouped[fid].append(r)

        print(f"Found {len(grouped)} unique assets to migrate.")

        new_assets = 0
        new_runs = 0

        for fid, runs in grouped.items():
            # Check if asset exists
            existing_asset = session.query(UploadedAsset).filter(UploadedAsset.storage_key == f"gdrive:{fid}").first()
            
            if existing_asset:
                asset = existing_asset
                # print(f"Asset {fid} already exists.")
            else:
                if args.dry_run:
                    # Mock
                    asset = UploadedAsset(id=0)
                else:
                    # Determine overall status
                    # If any successful run, we consider asset processed? 
                    # Or simple logic: READY
                    asset = AssetService.create_uploaded_asset(
                        session,
                        account_id=account.id,
                        storage_key=f"gdrive:{fid}",
                        original_filename=f"{fid}.mp4",
                        status="READY", # Assume migrated assets are processed
                        uploaded_by_email="migration_script"
                    )
                    new_assets += 1

            for r in runs:
                platform = r["platform"].upper() # DB uses caps per plan? or lower?
                # Models default is String. Job uses lower. Plan said: values like "YOUTUBE".
                # Let's standardize on UPPER in DB for enums usually, but job logic mapped .lower().
                # Job logic: `platform_key = run.target_platform.lower()` 
                # So if I store UPPER, job handles it.
                
                status_map = {
                    "success": "SUCCESS",
                    "failed": "FAILED",
                    "skipped": "SUCCESS" # Treat skipped as success (idempotency)
                }
                status = status_map.get(r["status"], "PENDING")
                
                # Check if run exists
                if not args.dry_run:
                    # Ideally check duplicate?
                    # Using Asset + Platform uniqueness check?
                    # For now just create.
                    exists = session.query(PublishingRunPost).filter(
                        PublishingRunPost.asset_id == asset.id,
                        PublishingRunPost.target_platform == platform
                    ).first()
                    
                    if exists:
                        continue

                    run = PublishingRunService.create_publishing_run(
                        session,
                        account_id=account.id,
                        asset_id=asset.id,
                        target_platform=platform,
                    )
                    # Force status update
                    PublishingRunService.update_run_status(
                        session, run.id, status, error_message="Migrated from JSON"
                    )
                    
                    # Create content
                    PublishingRunService.create_publishing_run_content(
                        session,
                        publishing_run_post_id=run.id,
                        description=f"Migrated content for {fid}"
                    )
                    new_runs += 1

        if args.dry_run:
            print(f"[DRY RUN] Would create ~{len(grouped)} assets and {len(records)} runs.")
        else:
            print(f"Migration complete. Created {new_assets} assets and {new_runs} runs.")

    except Exception as e:
        print(f"Error migrating state: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    main()
