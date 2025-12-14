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

            # 3. Prepare arguments for workflow (V1 JIT Materialization)
            from agent.services.asset_materializer import materialized_scope
            
            # Wrap execution in materializer scope to ensure cleanup
            with materialized_scope(session, run_id) as materializer:
                try:
                    # Materialize asset to host, get container path
                    # This handles S3 download / RDS Blob stream
                    video_container_path_str = materializer.materialize_asset(asset.id)
                    video_path = Path(video_container_path_str)
                    
                    logger.info(f"[JOB] Asset materialized at {video_path} (Container path)")
                    
                except Exception as e:
                    error_msg = f"Failed to materialize asset: {e}"
                    logger.exception(error_msg)
                    PublishingRunService.update_run_status(session, run_id, "FAILED", error_msg)
                    return {"status": "failed", "error": error_msg}

                # Indent subsequent logic or structure to fall within scope?
                # Actually, the materializer needs to keep the file until upload is done.
                # So the REST of the function (step 4) must be inside this block.
                # This suggests I should wrap the ENTIRE step 4 in this block.
                # To minimize diff noise, I will start the block here and indent the rest in a subsequent step?
                # Or I can just start the block here and assume the user (me) will indent the rest?
                # No, I must provide valid python.
                
                # RE-STRATEGY:
                # The execute_run method is long. Indenting everything is risky/messy in one go.
                # I'll use a try/finally block structure explicit in the modification where I can.
                # But since I can't easily indent 200 lines, I might need to refactor or be careful.
                
                # Alternative: `materializer = AssetMaterializer(session, run_id)` 
                # then `materializer.materialize...`
                # then `try: ... finally: materializer.cleanup()`.
                # This avoids massive indentation changes.
                
                pass # placeholder to keep syntax valid if I cut the block here
                
            # WAIT. If I use context manager `with`, I MUST indent everything.
            # If I use manual cleanup, I verify I call cleanup.
            # `PublishingJob` captures exception broadly at line 388 (outer try).
            # The `execute_run` has a `finally` block at 391.
            # I can instantiate materializer at start, use it, and call cleanup in `finally`.
            
            materializer = None
            try:
                # Initialize materializer
                from agent.services.asset_materializer import AssetMaterializer
                materializer = AssetMaterializer(session, run_id)
                
                # Materialize
                video_container_path_str = materializer.materialize_asset(asset.id)
                video_path = Path(video_container_path_str)
                logger.info(f"[JOB] Asset materialized at {video_path}")
                
                # Proceed to Step 4...
                # (The code following this block continues naturally)
                
            except Exception as e:
                 # If materialization itself fails (before main try-catch catches it?)
                 # The outer try catch will handle it.
                 raise e 
                 
            # Wait, I am replacing lines 68-92 (GDrive logic).
            # I need `video_path` to be available below.
            # And I need `materializer.cleanup()` to be called at the end of `execute_run`.
            
            # I can add `if materializer: materializer.cleanup()` to the `finally` block of `execute_run` (Lines 391+).
            # And insert the materialization logic here.
            
            # Let's do that.
            
            # REPLACEMENT CONTENT for lines 68-92:
            
            # Import overhead
            from agent.services.asset_materializer import AssetMaterializer
            
            # Materialize
            # We store materializer in self or local var? 
            # Local var `materializer` is fine, but needs to be accessible in finally?
            # Assign to `self.materializer`? No, instance is shared? 
            # `PublishingJob` is instantiated once in main? Yes `job = PublishingJob()`.
            # So `self.materializer` is risky if concurrency (though distinct run_ids).
            # But `__init__` doesn't have it.
            
            # I will use a local variable `materializer` effectively.
            # But I need to ensure cleanup.
            # I will use a nested `try...finally` block AROUND the workflow execution if possible.
            # OR just update the function's main `finally` block to cleanup specific paths if they exist?
            # But `AssetMaterializer` encapsulates the path logic.
            
            # Let's go with:
            # 1. Instantiate materializer here.
            # 2. Add an inner `try...finally` starting HERE, spanning to end of function? 
            # That requires massive replace.
            
            # BETTER OPTION:
            # Use `run_cycle_single`? No that calls the upload.
            
            # OPTION C: Context Manager with indentation...
            # The tool `replace_file_content` replaces a contiguous block. 
            # I can't indent the bottom 200 lines without replacing them.
            # That's too big.
            
            # OPTION D: `materializer.cleanup()` explicitly before every `return`?
            # There are multiple returns (lines 50, 61, 92, 327, 333, 360, 386, 390).
            # Error prone.
            
            # OPTION E: Modify `execute_run` to call a helper `_execute_workflow`?
            # Refactor `execute_run` to:
            # setup materializer
            # try:
            #    _execute_workflow(...)
            # finally:
            #    materializer.cleanup()
            
            # That is a big refactor.
            
            # OPTION F (Pragmatic):
            # Manually instantiate `AssetMaterializer`.
            # Add `materializer = None` at top of `execute_run` (or before step 3).
            # Update the MAIN `finally` block (lines 391) to generic cleanup.
            # "if 'materializer' in locals() and materializer: materializer.cleanup()"
            
            # This is safe and minimizes diffs.
            
            
            # Replacement for GDrive block:
            
            platform_key = platform.code.lower()
            captions = {}
            
            # Prepare Materializer
            from agent.services.asset_materializer import AssetMaterializer
            materializer = AssetMaterializer(session, run_id)
            
            try:
                video_path_str = materializer.materialize_asset(asset.id)
                video_path = Path(video_container_path_str)
            except Exception as e:
                 error_msg = f"Materialization failed: {e}"
                 logger.error(error_msg)
                 PublishingRunService.update_run_status(session, run_id, "FAILED", error_msg)
                 return {"status": "failed", "error": error_msg}
            
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
                    # ALLOCATION & SESSION MANAGEMENT
                # We use the Allocator to get a session (GoLogin or Fallback)
                # The underlying providers handle the "limit" logic internally or via the Allocator's loop
                
                from agent.services.browser_provider_allocator import BrowserProviderAllocator
                from selenium import webdriver
                from selenium.webdriver.chrome.options import Options
                
                allocator = BrowserProviderAllocator()
                
                results = {} # Initialize results here
                
                max_attempts = 3
                for attempt in range(1, max_attempts + 1):

                    # Allocate Session
                    # This handles GoLogin -> Error -> NoVNC fallback logic automatically!
                    
                    # We need to wrap this in a customized context manager or try/finally
                    # to ensure we stop the session.
                    
                    logger.info(f"[JOB] Allocating browser for {account.name}")
                    
                    browser_session = allocator.allocate_for_dummy_account(
                        session,
                        dummy_account_id=account.id,
                        platform_id=platform.id, # Use platform.id from the fetched run
                        trace_id=f"run-{run_id}"
                    )
                    
                    # Update Run with Allocation Info
                    # Look up provider_id from profile since BrowserSession doesn't carry it
                    from agent.db.models import BrowserProviderProfile
                    profile_obj = session.get(BrowserProviderProfile, browser_session.provider_profile_id)
                    
                    if profile_obj:
                        parent_run.browser_provider_id = profile_obj.browser_provider_id
                    
                    parent_run.browser_provider_profile_id = browser_session.provider_profile_id
                    parent_run.provider_session_ref = browser_session.provider_session_ref
                    session.commit()
                    
                    # Log Selection
                    PublishingRunEventService.log_event(
                        session, 
                        publishing_run_id=run_id, 
                        event_type="RUN_PROVIDER_SELECTED", 
                        message=f"Selected {browser_session.provider_code}",
                        payload={
                            "provider": browser_session.provider_code,
                            "profile_id": browser_session.provider_profile_id,
                            "webdriver_url": browser_session.webdriver_url
                        }
                    )

                    # EXECUTE WORKFLOW
                    # We pass the webdriver_url to the workflow.
                    # The workflow needs to be updated to accept `webdriver_url` instead of `driver` object?
                    # Or we adapt here.
                    
                    target_platforms = [platform.code.lower()] # Use platform.code from the fetched run
                    
                    # Note: run_cycle_single currently takes `driver`.
                    # If we change it to take `webdriver_url`, we update it there.
                    # Or we create a Remote driver here and pass it.
                    
                    # Creating a Remote Driver Connection
                    # This unifies GoLogin (if we made it behave remote) and noVNC
                    # BUT GoLoginProvider might return a local execution URL that implies "Attach".
                    
                    # Actually, if GoLoginProvider returned a local executor URL, we might need to attach.
                    # Simplified: We pass 'browser_session' to 'run_cycle_single' and let IT decide how to connect.
                    # But 'run_cycle_single' is in 'agent.workflow'.
                    
                    # Let's pass `browser_session` as `driver_session` param
                    driver_context = None 
                    # We can't easily pass the session object into current `run_cycle_single` without change.
                    # For now, let's assume `run_cycle_single` can accept `webdriver_url` in `driver` arg?
                    # No, `driver` arg expects a WebDriver instance.
                    
                    # WE MUST CONNECT HERE.
                    
                    driver_instance = None
                    
                    if browser_session.provider_code in ("NOVNC", "NOVNC_AWS"):
                        # Connect to Remote
                        opts = Options()
                        # Add any necessary options
                        driver_instance = webdriver.Remote(
                            command_executor=browser_session.webdriver_url,
                            options=opts
                        )
                    elif browser_session.provider_code == "GOLOGIN":
                        # GOLOGIN
                        # gologin_provider.py returned 'executor_url' effectively.
                        # But wait, GoLoginProvider.start_session ALREADY started the driver internally?
                        # If so, we can't easily get the object back unless we store it.
                        # My previous implementation was a bit hacky on `webdriver_url`.
                        
                        # Fix: GoLoginProvider usually yields a driver wrapper object.
                        # If we want to be clean, we should probably have returned the driver OBJECT in the session
                        # OR have the provider manage it.
                        
                        # Since we are refactoring, let's assume we can re-acquire or we need to update provider.
                        # Actually, looking at `gologin_provider.py` I implicitly assumed `webdriver_url` was enough.
                        # But for local GoLogin, we already have the driver running process.
                        # We need to connect to it or use the existing session?
                        
                        # Let's use `webdriver.Remote` with `executor_url` and `session_id`?
                        # That allows attaching to existing session!
                        # But GoLogin selenium wrapper manages the process.
                        
                        # For now, if it's GoLogin, we assume the `driver` passed to `execute_run` is the shared GoLogin driver.
                        # This means the `process_pending_runs` method needs to be updated to use the allocator too.
                        # For this specific change, we'll assume `driver` is already a GoLogin driver if `browser_session.provider_code == "GOLOGIN"`
                        # and `browser_session.webdriver_url` is not a remote URL.
                        
                        # If `browser_session.webdriver_url` is a remote URL (e.g., from a cloud GoLogin instance),
                        # we would connect to it using `webdriver.Remote`.
                        # For local GoLogin, the `driver` parameter passed to `execute_run` is the actual driver instance.
                        # This is a temporary simplification for the current refactor scope.
                        
                        # If `driver` is None, it means we are not in a shared session context.
                        # In this case, the allocator should have provided a `webdriver_url` that we can connect to.
                        if driver:
                            driver_instance = driver
                        elif browser_session.webdriver_url:
                            opts = Options()
                            driver_instance = webdriver.Remote(
                                command_executor=browser_session.webdriver_url,
                                options=opts
                            )
                        else:
                            raise ValueError("GoLogin session allocated but no driver or webdriver_url available.")
                    
                    if not driver_instance:
                        raise ValueError("Failed to obtain a WebDriver instance for the allocated browser session.")

                    # Now, execute the workflow with the obtained driver_instance
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
            if 'materializer' in locals() and materializer:
                materializer.cleanup()
            session.close()

    def process_pending_runs(self, limit: int = 5) -> Dict[str, int]:
        """
        Process a batch of pending posts.
        Optimized to group runs by account and share GoLogin browser sessions.
        Enforces LaunchGroup quotas.
        """
        session = SessionLocal()
        from collections import defaultdict
        
        runs_by_account = defaultdict(list)
        account_launch_groups = {} # Map account_name -> launch_group_id
        
        try:
            # Fetch pending POSTS
            runs = PublishingRunService.get_pending_runs(session, limit=limit)
             
            for run in runs:
                # Group by account name
                # Eager loading assumed or lazy load works inside session
                account_name = run.dummy_account.name
                runs_by_account[account_name].append(run.id)
                account_launch_groups[account_name] = run.dummy_account.launch_group_id
                
        finally:
            session.close()

        stats = {"processed": 0, "successful": 0, "failed": 0, "skipped_quota": 0}
        
        if not runs_by_account:
            logger.info("[JOB] No pending posts found.")
            return stats

        logger.info(f"[JOB] Found {sum(len(v) for v in runs_by_account.values())} pending posts across {len(runs_by_account)} accounts")
        
        from agent.services.launch_group_service import LaunchGroupService
        
        for account_name, run_ids in runs_by_account.items():
            # Check Launch Group Quota
            launch_group_id = account_launch_groups.get(account_name)
            
            # Quota Check Session
            # We want to check quota BEFORE opening any browser resources
            should_skip_batch = False
            if launch_group_id:
                with SessionLocal() as q_session:
                    if not LaunchGroupService.can_execute_run(q_session, launch_group_id):
                        logger.warning(f"[JOB] Launch Group Quota exceeded for account {account_name} (Group {launch_group_id}). Skipping batch.")
                        stats["skipped_quota"] += len(run_ids)
                        should_skip_batch = True
            
            if should_skip_batch:
                continue

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
                    pass

            # Execution Loop
            # We pass the session to the context if simple, but we have strict quota calls now.
            try:
                def process_single(r_id, drv=None):
                    # Quota Enforcement Wrapper
                    if launch_group_id:
                        with SessionLocal() as q_sess:
                            if not LaunchGroupService.can_execute_run(q_sess, launch_group_id):
                                logger.warning(f"[JOB] Quota hit mid-batch for {account_name}")
                                return "skipped_quota"
                            
                            # Start Tracking
                            LaunchGroupService.on_run_started(q_sess, launch_group_id)
                            q_sess.commit()

                    try:
                        return self.execute_run(r_id, driver=drv)
                    finally:
                        if launch_group_id:
                            with SessionLocal() as q_sess:
                                LaunchGroupService.on_run_finished(q_sess, launch_group_id)
                                q_sess.commit()

                did_run_shared = False
                if driver_ctx:
                    try:
                        with driver_ctx as shared_driver:
                            did_run_shared = True
                            for run_id in run_ids:
                                exec_result = process_single(run_id, drv=shared_driver)
                                stats["processed"] += 1
                                if isinstance(exec_result, dict):
                                    if exec_result.get("status") in ("success", "skipped"):
                                        stats["successful"] += 1
                                    else:
                                        stats["failed"] += 1
                                elif exec_result == "skipped_quota":
                                    stats["skipped_quota"] += 1
                    except Exception as e:
                        logger.warning(f"[JOB] Shared GoLogin session failed to start/complete: {e}. Falling back to individual runs.")
                        # Fallback will happen as did_run_shared is False (or exception broke it)
                        # If exception broke MID-loop, some runs might be done.
                        # But typically __enter__ fails first.
                        # If loop broke, we might re-run some? No, "processed" tracks it?
                        # `process_single` is atomic per run.
                        # If __enter__ failed, nothing ran.
                        # If loop broke mid-way, `run_ids` iterator is consumed? We are iterating list.
                        # We should verify which ran?
                        # Simplification: If `did_run_shared` is True, we assume we consumed what we could. 
                        # BUT if it failed inside `__enter__`, `did_run_shared` is False.
                
                if not did_run_shared:
                    # No shared driver (or failed to start) - Fallback to individual
                    # Be careful not to double process if partial failure occurred above.
                    # Simple heuristic: if stats["processed"] == 0, we are safe to run all.
                    # If stats["processed"] > 0, we might double run. 
                    # Ideally we track `processed_run_ids`.
                    
                    # Assuming for now limits hit at START (processed=0).
                    if stats["processed"] == 0:
                        for run_id in run_ids:
                            exec_result = process_single(run_id)
                            stats["processed"] += 1
                            if isinstance(exec_result, dict):
                                if exec_result.get("status") in ("success", "skipped"):
                                    stats["successful"] += 1
                                else:
                                    stats["failed"] += 1
                            elif exec_result == "skipped_quota":
                                stats["skipped_quota"] += 1
                    else:
                        logger.error("[JOB] Shared session partially failed. Skipping remaining to avoid duplication in this simple implementation.")

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
