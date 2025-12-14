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
from agent.services.publishing_run_events import PublishingRunEventService
from agent.workflow import run_cycle_single

# Updated Model Import
from agent.db.models import PublishingPost

class PublishingJob:
    """Job to process publishing runs (Modernized for Schema v2)."""

    def __init__(self):
        self.settings = load_settings()

    from collections import defaultdict
    from tools.gologin_selenium import SyncGoLoginWebDriver

    def execute_run(self, run_id: int, driver=None) -> Dict[str, Any]:
        """Execute a single publishing run (post)."""
        session = SessionLocal()
        try:
            # 1. Fetch run (Post) and dependencies
            run = session.get(PublishingPost, run_id)
            if not run:
                logger.error(f"[JOB] Post {run_id} not found")
                return {"status": "error", "message": "Post not found"}
            
            # Access relationships
            # Note: We assume 1 asset per post for now
            if not run.assets:
                msg = f"No assets found for post {run_id}"
                logger.error(f"[JOB] {msg}")
                PublishingRunService.update_run_status(session, run_id, "FAILED", msg)
                return {"status": "failed", "error": msg}
            
            asset = run.assets[0].asset
            content = run.content
            platform = run.platform
            account = run.dummy_account
            
            if not asset:
                msg = f"Asset link broken for post {run_id}"
                logger.error(f"[JOB] {msg}")
                PublishingRunService.update_run_status(session, run_id, "FAILED", msg)
                return {"status": "failed", "error": msg}

            # 2. Update status to RUNNING
            logger.info(f"[JOB] Starting post {run_id} for {platform.code} (Asset {asset.id})")
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
                     
                     local_path = temp_dir / asset.original_name
                     logger.info(f"Downloading {asset.storage_key} to {local_path}...")
                     
                     download_video(service, asset.storage_key, local_path)
                     video_path = local_path.resolve()
                     logger.success(f"Download complete: {video_path}")
                     
                 except Exception as e:
                     error_msg = f"Failed to download asset from GDrive: {e}"
                     logger.error(error_msg)
                     PublishingRunService.update_run_status(session, run_id, "FAILED", error_msg)
                     return {"status": "failed", "error": error_msg}

            platform_key = platform.code.lower()
            captions = {}
            
            # Map content to platform-specific format
            if platform_key in ("tiktok", "instagram"):
                captions[platform_key] = content.description or ""
            elif platform_key == "youtube":
                captions["youtube"] = {
                    "title": content.title or asset.original_name,
                    "description": content.description or "",
                    "tags": content.tags or [],
                    "publish_at": run.scheduled_at
                }

            # 4. Execute workflow with provider fallback
            try:
                # Extract browser profile info from parent run
                parent_run = run.run  # PublishingRun
                current_profile_id = None
                current_profile_ref = None
                current_provider_code = None
                gologin_token = None
                
                if parent_run and parent_run.browser_profile:
                    current_profile_id = parent_run.browser_provider_profile_id
                    current_profile_ref = parent_run.browser_profile.provider_profile_ref
                    current_provider_code = parent_run.browser_profile.provider.code
                    # Get token from settings
                    for config in self.settings.gologin_accounts.values():
                        gologin_token = config.token
                        break
                    logger.info(f"[JOB] Using allocated profile {current_profile_ref} ({current_provider_code}) for {account.name}")
                
                # Retry loop with provider fallback
                max_attempts = 2
                attempt = 0
                last_error = None
                
                while attempt < max_attempts:
                    attempt += 1
                    
                    # Only pass GoLogin credentials if provider is GoLogin
                    gologin_profile_id_param = current_profile_ref if current_provider_code == 'GOLOGIN' else None
                    gologin_token_param = gologin_token if current_provider_code == 'GOLOGIN' else None
                    
                    logger.info(f"[JOB] Attempt {attempt}/{max_attempts} using provider {current_provider_code}")
                    
                    results = run_cycle_single(
                         self.settings,
                         video_path,
                         captions,
                         target_platforms=[platform_key],
                         drive_file_id=asset.storage_key,
                         account_name=account.name,
                         driver=driver,
                         gologin_token=gologin_token_param,
                         gologin_profile_id=gologin_profile_id_param
                    )
                    
                    platform_result = results.get(platform_key, {})
                    status = platform_result.get("status")
                    error_msg = platform_result.get("error", "")
                    
                    # Check if this is a provider-specific failure that can be retried
                    is_provider_error = "GoLogin" in error_msg or "limit" in error_msg.lower() or "gologin" in error_msg.lower()
                    
                    if status == "success" or status == "skipped":
                        # Success! Return the result
                        break
                    elif is_provider_error and attempt < max_attempts:
                        # Provider failed, try fallback
                        logger.warning(f"[JOB] Provider {current_provider_code} failed, attempting fallback...")
                        
                        # Log the provider error
                        from agent.services.browser_provider_allocator import BrowserProviderAllocator
                        PublishingRunEventService.log_provider_error(
                            session,
                            publishing_run_id=run.publishing_run_id,
                            error_code=PublishingRunEventService.ERROR_GOLOGIN_LIMIT,
                            message=f"Provider {current_provider_code} failed, trying fallback",
                            provider_code=current_provider_code,
                            profile_ref=current_profile_ref
                        )
                        
                        # Get fallback profile
                        fb_provider_id, fb_profile_id, fb_profile_ref, fb_provider_code = BrowserProviderAllocator.get_fallback_profile(
                            session, account.id, current_provider_code
                        )
                        
                        if fb_profile_ref:
                            logger.info(f"[JOB] Falling back to {fb_provider_code}: {fb_profile_ref}")
                            current_profile_id = fb_profile_id
                            current_profile_ref = fb_profile_ref
                            current_provider_code = fb_provider_code
                        else:
                            logger.error(f"[JOB] No fallback provider available")
                            last_error = error_msg
                            break
                    else:
                        # Non-provider error or no more attempts
                        last_error = error_msg
                        break
                
                # Handle final result
                
                # 5. Handle result
                platform_result = results.get(platform_key, {})
                status_code = platform_result.get("status")
                
                if status_code == "success":
                    PublishingRunService.update_run_status(
                        session, run_id, "SUCCESS"
                    )
                    logger.info(f"[JOB] Post {run_id} SUCCEEDED")
                    return {"status": "success", "platform_result": platform_result}
                elif status_code == "skipped":
                     PublishingRunService.update_run_status(
                        session, run_id, "SUCCESS", error_message="Skipped (already uploaded)"
                    )
                     logger.info(f"[JOB] Post {run_id} SKIPPED")
                     return {"status": "skipped", "platform_result": platform_result}
                else:
                    error_msg = platform_result.get("error", "Unknown error")
                    PublishingRunService.update_run_status(
                        session, run_id, "FAILED", error_message=error_msg
                    )
                    
                    # Log provider error if GoLogin related
                    if "GoLogin" in error_msg or "gologin" in error_msg.lower() or "limit" in error_msg.lower():
                        error_code = PublishingRunEventService.ERROR_GOLOGIN_LIMIT if "limit" in error_msg.lower() else PublishingRunEventService.ERROR_GOLOGIN_PROFILE
                        PublishingRunEventService.log_provider_error(
                            session,
                            publishing_run_id=run.publishing_run_id,
                            error_code=error_code,
                            message=error_msg[:500],
                            provider_code="GOLOGIN",
                            profile_ref=gologin_profile_id
                        )
                    else:
                        PublishingRunEventService.log_run_failed(
                            session,
                            publishing_run_id=run.publishing_run_id,
                            error_message=error_msg[:500],
                            publishing_post_id=run_id
                        )
                    
                    logger.error(f"[JOB] Post {run_id} FAILED: {error_msg}")
                    return {"status": "failed", "error": error_msg}

            except Exception as e:
                error_str = str(e)
                logger.exception(f"[JOB] Exception executing post {run_id}")
                PublishingRunService.update_run_status(session, run_id, "FAILED", error_str)
                
                # Log provider error if applicable
                if "GoLogin" in error_str or "gologin" in error_str.lower():
                    error_code = PublishingRunEventService.ERROR_GOLOGIN_LIMIT if "limit" in error_str.lower() else PublishingRunEventService.ERROR_GOLOGIN_PROFILE
                    PublishingRunEventService.log_provider_error(
                        session,
                        publishing_run_id=run.publishing_run_id,
                        error_code=error_code,
                        message=error_str[:500],
                        provider_code="GOLOGIN",
                        profile_ref=gologin_profile_id,
                        exception_details=error_str
                    )
                else:
                    PublishingRunEventService.log_run_failed(
                        session,
                        publishing_run_id=run.publishing_run_id,
                        error_message=error_str[:500],
                        publishing_post_id=run_id
                    )
                return {"status": "failed", "error": error_str}

        except Exception as e:
            logger.exception(f"[JOB] System error in post {run_id}")
            return {"status": "system_error", "error": str(e)}
        finally:
            session.close()

    def process_pending_runs(self, limit: int = 5) -> Dict[str, int]:
        """
        Process a batch of pending posts.
        Optimized to group runs by account and share GoLogin browser sessions.
        """
        session = SessionLocal()
        from collections import defaultdict
        
        runs_by_account = defaultdict(list)
        try:
            # Fetch pending POSTS
            runs = PublishingRunService.get_pending_runs(session, limit=limit)
             
            for run in runs:
                # Group by account name
                # Eager loading assumed or lazy load works.
                account_name = run.dummy_account.name
                runs_by_account[account_name].append(run.id)
                
        finally:
            session.close()

        stats = {"processed": 0, "successful": 0, "failed": 0}
        
        if not runs_by_account:
            logger.info("[JOB] No pending posts found.")
            return stats

        logger.info(f"[JOB] Found {sum(len(v) for v in runs_by_account.values())} pending posts across {len(runs_by_account)} accounts")
        
        for account_name, run_ids in runs_by_account.items():
            logger.info(f"[JOB] Processing batch for account: {account_name} ({len(run_ids)} posts)")
            
            # GoLogin Logic
            creds = self.settings.get_gologin_credentials(account_name)
            driver = None
            driver_ctx = None
            
            # Helper to import inside method to avoid early import issues if needed
            from tools.gologin_selenium import SyncGoLoginWebDriver
            
            if creds:
                token, profile_id = creds
                logger.info(f"[JOB] Opening shared GoLogin session for {account_name} (Profile {profile_id})")
                try:
                    driver_ctx = SyncGoLoginWebDriver(token, profile_id)
                except Exception as e:
                    logger.error(f"[JOB] Failed to start GoLogin session for {account_name}: {e}")
                    # Allow fallback?
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
                    # No shared driver
                    for run_id in run_ids:
                        result = self.execute_run(run_id) 
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
    parser = argparse.ArgumentParser(description="Publishing Job Runner (Schema v2)")
    parser.add_argument("--run-id", type=int, help="Execute a specific post ID")
    parser.add_argument("--limit", type=int, default=5, help="Number of pending posts to process")
    parser.add_argument("--loop", action="store_true", help="Run in a loop")
    
    args = parser.parse_args()
    
    job = PublishingJob()
    
    if args.run_id:
        job.execute_run(args.run_id)
    elif args.loop:
        logger.info("Starting polling loop...")
        while True:
            job.process_pending_runs(limit=args.limit)
            time.sleep(60)
    else:
        job.process_pending_runs(limit=args.limit)

if __name__ == "__main__":
    main()
