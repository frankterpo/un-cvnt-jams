"""Job runner for executing publishing runs."""
from __future__ import annotations

import sys
import argparse
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger
from dotenv import load_dotenv

# Load env immediately to ensure DATABASE_URL is set for DB base
load_dotenv()

from agent.db.base import SessionLocal
from agent.config import load_settings
from agent.services.publishing_runs import PublishingRunService
from agent.services.assets import AssetService
from agent.workflow import run_cycle_single

from agent.db.models import PublishingRunPost

class PublishingJob:
    """Job to process publishing runs."""

    def __init__(self):
        self.settings = load_settings()

    from collections import defaultdict
    from tools.gologin_selenium import SyncGoLoginWebDriver

    def execute_run(self, run_id: int, driver=None) -> Dict[str, Any]:
        """Execute a single publishing run."""
        session = SessionLocal()
        try:
            # 1. Fetch run and dependencies
            run = session.get(PublishingRunPost, run_id) # Type hint fix needed if strict
            if not run:
                logger.error(f"[JOB] Run {run_id} not found")
                return {"status": "error", "message": "Run not found"}
            
            # Re-fetch via service or just access relationships lazy loaded
            asset = run.asset
            content = run.content
            
            if not asset:
                msg = f"Asset not found for run {run_id}"
                logger.error(f"[JOB] {msg}")
                PublishingRunService.update_run_status(session, run_id, "FAILED", msg)
                return {"status": "failed", "error": msg}

            # 2. Update status to RUNNING
            logger.info(f"[JOB] Starting run {run_id} for {run.target_platform} (Asset {asset.id})")
            PublishingRunService.update_run_status(session, run_id, "RUNNING")

            # 3. Prepare arguments for workflow
            video_path = Path(asset.storage_key)
            if not video_path.exists():
                 logger.info(f"File {video_path} not found locally. Attempting GDrive download...")
                 try:
                     from agent.source_gdrive import build_drive_client, download_video
                     import os
                     
                     sa_json = os.getenv("GDRIVE_SA_JSON", "blissful-fiber-473419-e6-abf91b637595.json")
                     service = build_drive_client(Path(sa_json))
                     
                     temp_dir = Path("pipeline_output/videos")
                     temp_dir.mkdir(parents=True, exist_ok=True)
                     
                     local_path = temp_dir / asset.original_filename
                     logger.info(f"Downloading {asset.storage_key} to {local_path}...")
                     
                     download_video(service, asset.storage_key, local_path)
                     video_path = local_path.resolve()
                     logger.success(f"Download complete: {video_path}")
                     
                 except Exception as e:
                     error_msg = f"Failed to download asset from GDrive: {e}"
                     logger.error(error_msg)
                     PublishingRunService.update_run_status(session, run_id, "FAILED", error_msg)
                     return {"status": "failed", "error": error_msg}

            platform_key = run.target_platform.lower()
            captions = {}
            
            # Map content to platform-specific format
            if platform_key in ("tiktok", "instagram"):
                captions[platform_key] = content.description or ""
            elif platform_key == "youtube":
                captions["youtube"] = {
                    "title": content.title or asset.original_filename,
                    "description": content.description or "",
                    "tags": content.tags or [],
                    "publish_at": run.scheduled_at
                }

            # 4. Execute workflow
            try:
                # Pass driver if provided (Batch mode optimization)
                results = run_cycle_single(
                     self.settings,
                     video_path,
                     captions,
                     target_platforms=[platform_key],
                     drive_file_id=asset.storage_key,
                     account_name=run.account.name,
                     driver=driver
                )
                
                # 5. Handle result
                platform_result = results.get(platform_key, {})
                status_code = platform_result.get("status")
                
                if status_code == "success":
                    PublishingRunService.update_run_status(
                        session, run_id, "SUCCESS"
                    )
                    logger.info(f"[JOB] Run {run_id} SUCCEEDED")
                    return {"status": "success", "platform_result": platform_result}
                elif status_code == "skipped":
                     PublishingRunService.update_run_status(
                        session, run_id, "SUCCESS", error_message="Skipped (already uploaded)"
                    )
                     logger.info(f"[JOB] Run {run_id} SKIPPED")
                     return {"status": "skipped", "platform_result": platform_result}
                else:
                    error_msg = platform_result.get("error", "Unknown error")
                    PublishingRunService.update_run_status(
                        session, run_id, "FAILED", error_message=error_msg
                    )
                    logger.error(f"[JOB] Run {run_id} FAILED: {error_msg}")
                    return {"status": "failed", "error": error_msg}

            except Exception as e:
                logger.exception(f"[JOB] Exception executing run {run_id}")
                PublishingRunService.update_run_status(session, run_id, "FAILED", str(e))
                return {"status": "failed", "error": str(e)}

        except Exception as e:
            logger.exception(f"[JOB] System error in run {run_id}")
            return {"status": "system_error", "error": str(e)}
        finally:
            session.close()

    def process_pending_runs(self, limit: int = 5) -> Dict[str, int]:
        """
        Process a batch of pending runs.
        Optimized to group runs by account and share GoLogin browser sessions.
        """
        session = SessionLocal()
        runs_by_account = defaultdict(list)
        try:
            # Increase limit for batching efficiency if we are grouping
            # Or respect the limit but spread it? 
            # If limit is 5, we get 5 runs. Even if all 5 are same account, we save 4 launches.
            runs = PublishingRunService.get_pending_runs(session, limit=limit)
             
             # Group by account name for batch processing
            for run in runs:
                # Eager load account to avoid detached instance issues later if we close session
                # Actually we can just store ID/Name tuple or keep object attached? 
                # Better to use ID for grouping.
                account_name = run.account.name
                runs_by_account[account_name].append(run.id)
                
        finally:
            session.close() # We re-fetch in execute_run so safe to close

        stats = {"processed": 0, "successful": 0, "failed": 0}
        
        if not runs_by_account:
            logger.info("[JOB] No pending runs found.")
            return stats

        logger.info(f"[JOB] Found {sum(len(v) for v in runs_by_account.values())} pending runs across {len(runs_by_account)} accounts")
        
        for account_name, run_ids in runs_by_account.items():
            logger.info(f"[JOB] Processing batch for account: {account_name} ({len(run_ids)} runs)")
            
            # 1. Determine if we need GoLogin session for this account
            creds = self.settings.get_gologin_credentials(account_name)
            driver = None
            driver_ctx = None
            
            if creds:
                token, profile_id = creds
                logger.info(f"[JOB] Opening shared GoLogin session for {account_name} (Profile {profile_id})")
                try:
                    driver_ctx = SyncGoLoginWebDriver(token, profile_id)
                except Exception as e:
                    logger.error(f"[JOB] Failed to start GoLogin session for {account_name}: {e}")
                    # If driver fails, maybe try runs individually (they will fail there too likely)
                    # or skip batch. Let's mark them failed?
                    # Or proceed without driver and let execute_run try/fail individually?
                    # Proceeding without driver allows fallback to local logic if applicable (e.g. dev mode)
                    pass

            try:
                if driver_ctx:
                    with driver_ctx as shared_driver:
                        for run_id in run_ids:
                            result = self.execute_run(run_id, driver=shared_driver)
                            stats["processed"] += 1
                            if result.get("status") in ("success", "skipped"):
                                stats["successful"] += 1
                            else:
                                stats["failed"] += 1
                else:
                    # No shared driver (local account or failed launch), process normally (individual launches if needed)
                    for run_id in run_ids:
                        result = self.execute_run(run_id) # No driver passed
                        stats["processed"] += 1
                        if result.get("status") in ("success", "skipped"):
                            stats["successful"] += 1
                        else:
                            stats["failed"] += 1
                            
            except Exception as e:
                 logger.exception(f"[JOB] Batch execution crashed for {account_name}: {e}")
                 
        logger.info(f"[JOB] Batch complete: {stats}")
        return stats

def main():
    parser = argparse.ArgumentParser(description="Publishing Job Runner")
    parser.add_argument("--run-id", type=int, help="Execute a specific run ID")
    parser.add_argument("--limit", type=int, default=5, help="Number of pending runs to process")
    parser.add_argument("--loop", action="store_true", help="Run in a loop")
    
    args = parser.parse_args()
    
    job = PublishingJob()
    
    if args.run_id:
        job.execute_run(args.run_id)
    elif args.loop:
        logger.info("Starting polling loop...")
        while True:
            job.process_pending_runs(limit=args.limit)
            time.sleep(60) # Poll every minute
    else:
        job.process_pending_runs(limit=args.limit)

if __name__ == "__main__":
    main()
