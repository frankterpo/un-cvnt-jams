"""Workflow integration for social media uploads with idempotency."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from loguru import logger

from agent.config import Settings
from agent.state import UploadState
# Lazy loaded in methods:
# from tools.tiktok_client import TikTokClient
# from tools.youtube_client import YouTubeClient
# from tools.youtube_metadata import YouTubeMetadata
# from tools.instagram_client import InstagramClient

from tools.gologin_selenium import SyncGoLoginWebDriver


class VideoItem:
    """Minimal abstraction for a video to post."""

    def __init__(self, id: str, path: Path, captions: dict):
        self.id = id
        self.path = path
        self.captions = captions  # {"tiktok": "...", "youtube": {...}, "instagram": "..."}


def _parse_publish_at(raw: object) -> datetime | None:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return None


def _get_driver_context(
    settings: Settings,
    account_name: str | None,
    gologin_token: str | None,
    gologin_profile_id: str | None,
    platform_tag: str = "WORKFLOW"
) -> SyncGoLoginWebDriver | None:
    """
    Create GoLogin driver context.
    
    Priority:
    1. Direct gologin_token + gologin_profile_id (from DB allocation)
    2. Lookup via account_name from settings (legacy)
    """
    if gologin_token and gologin_profile_id:
        logger.info(f"[{platform_tag}] Using allocated GoLogin profile {gologin_profile_id}")
        return SyncGoLoginWebDriver(gologin_token, gologin_profile_id)
    
    if account_name:
        creds = settings.get_gologin_credentials(account_name)
        if creds:
            token, profile_id = creds
            logger.info(f"[{platform_tag}] Using legacy GoLogin profile {profile_id} for {account_name}")
            return SyncGoLoginWebDriver(token, profile_id)
    
    return None


def _publish_tiktok(
    settings: Settings, 
    state: UploadState, 
    item: VideoItem, 
    account_name: str | None = None, 
    driver=None,
    gologin_token: str | None = None,
    gologin_profile_id: str | None = None
) -> dict:
    platform = "tiktok"
    if state.has_success(item.id, platform):
        logger.info("[TIKTOK] Skipping {} – already uploaded", item.id)
        return {"status": "skipped", "reason": "already_uploaded"}

    caption = item.captions.get("tiktok")
    if not caption:
        logger.info("[TIKTOK] No caption for {}, skipping", item.id)
        return {"status": "skipped", "reason": "missing_caption"}

    # Get GoLogin context if needed
    driver_ctx = None if driver else _get_driver_context(settings, account_name, gologin_token, gologin_profile_id, "TIKTOK")

    try:
        from tools.tiktok_client import TikTokClient
        
        if driver:
            client = TikTokClient(settings.tiktok)
            client.upload_single(item.path, caption, driver=driver)
        elif driver_ctx:
            with driver_ctx as local_driver:
                client = TikTokClient(settings.tiktok)
                client.upload_single(item.path, caption, driver=local_driver)
        else:
            client = TikTokClient(settings.tiktok)
            client.upload_single(item.path, caption)
             
        state.mark_success(item.id, platform)
        return {"status": "success"}
    except Exception as exc:
        logger.exception("[TIKTOK] Upload failed for {}", item.id)
        state.mark_failed(item.id, platform)
        return {"status": "failed", "error": str(exc)}


def _publish_youtube(
    settings: Settings, 
    state: UploadState, 
    item: VideoItem, 
    account_name: str | None = None, 
    driver=None,
    gologin_token: str | None = None,
    gologin_profile_id: str | None = None
) -> dict:
    platform = "youtube"
    if state.has_success(item.id, platform):
        logger.info("[YOUTUBE] Skipping {} – already uploaded", item.id)
        return {"status": "skipped", "reason": "already_uploaded"}

    ydata = item.captions.get("youtube")
    if not ydata:
        logger.info("[YOUTUBE] No metadata for {}, skipping", item.id)
        return {"status": "skipped", "reason": "missing_metadata"}

    from tools.youtube_client import YouTubeClient
    from tools.youtube_metadata import YouTubeMetadata

    meta = YouTubeMetadata(
        title=ydata["title"],
        description=ydata["description"],
        tags=ydata.get("tags", []),
        publish_at=_parse_publish_at(ydata.get("publish_at")),
    )


    
    driver_ctx = None if driver else _get_driver_context(settings, account_name, gologin_token, gologin_profile_id, "YOUTUBE")

    try:
        if driver:
            client = YouTubeClient(settings.youtube)
            video_id = client.upload_video(item.path, meta, driver=driver)
        elif driver_ctx:
            with driver_ctx as local_driver:
                client = YouTubeClient(settings.youtube)
                video_id = client.upload_video(item.path, meta, driver=local_driver)
        else:
            client = YouTubeClient(settings.youtube)
            video_id = client.upload_video(item.path, meta)
            
        state.mark_success(item.id, platform)
        return {"status": "success", "video_id": video_id}
    except Exception as exc:
        logger.exception("[YOUTUBE] Upload failed for {}", item.id)
        state.mark_failed(item.id, platform)
        return {"status": "failed", "error": str(exc)}


def _publish_instagram(
    settings: Settings, 
    state: UploadState, 
    item: VideoItem, 
    account_name: str | None = None, 
    driver=None,
    gologin_token: str | None = None,
    gologin_profile_id: str | None = None
) -> dict:
    platform = "instagram"
    if state.has_success(item.id, platform):
        logger.info("[INSTAGRAM] Skipping {} – already uploaded", item.id)
        return {"status": "skipped", "reason": "already_uploaded"}

    caption = item.captions.get("instagram")
    if not caption:
        logger.info("[INSTAGRAM] No caption for {}, skipping", item.id)
        return {"status": "skipped", "reason": "missing_caption"}

    driver_ctx = None if driver else _get_driver_context(settings, account_name, gologin_token, gologin_profile_id, "INSTAGRAM")

    try:
        from tools.instagram_client import InstagramClient
        
        if driver:
            client = InstagramClient(settings.instagram)
            client.upload(item.path, caption, post_type="feed", driver=driver)
        elif driver_ctx:
            with driver_ctx as local_driver:
                client = InstagramClient(settings.instagram)
                client.upload(item.path, caption, post_type="feed", driver=local_driver)
        else:
            client = InstagramClient(settings.instagram)
            client.upload(item.path, caption, post_type="feed")
            
        state.mark_success(item.id, platform)
        return {"status": "success"}
    except Exception as exc:
        logger.exception("[INSTAGRAM] Upload failed for {}", item.id)
        state.mark_failed(item.id, platform)
        return {"status": "failed", "error": str(exc)}


def run_cycle(
    settings: Settings,
    items: Iterable[VideoItem],
    platforms: list[str] | None = None,
    account_name: str | None = None,
    driver = None,
    gologin_token: str | None = None,
    gologin_profile_id: str | None = None,
) -> dict[str, dict[str, dict]]:
    """
    Iterate over video items and post to selected platforms with idempotency.
    
    Args:
        gologin_token: Direct GoLogin token (from DB browser_provider allocation)
        gologin_profile_id: Direct GoLogin profile ID (from DB browser_provider_profiles)
    """
    platforms = platforms or ["tiktok", "youtube", "instagram"]
    state = UploadState.load_default()
    all_results: dict[str, dict[str, dict]] = {}

    for item in items:
        item_results: dict[str, dict] = {}
        logger.info("[WORKFLOW] Processing item {} ({}) for account {}", item.id, item.path, account_name)

        if "tiktok" in platforms:
            item_results["tiktok"] = _publish_tiktok(settings, state, item, account_name, driver, gologin_token, gologin_profile_id)

        if "youtube" in platforms:
            item_results["youtube"] = _publish_youtube(settings, state, item, account_name, driver, gologin_token, gologin_profile_id)

        if "instagram" in platforms:
            item_results["instagram"] = _publish_instagram(settings, state, item, account_name, driver, gologin_token, gologin_profile_id)

        all_results[item.id] = item_results

    state.save()
    return all_results


def run_cycle_single(
    settings: Settings,
    video_path: Path,
    captions: dict,
    target_platforms: list[str] | None = None,
    drive_file_id: str | None = None,
    account_name: str | None = None,
    driver = None,
    gologin_token: str | None = None,
    gologin_profile_id: str | None = None,
) -> dict[str, dict]:
    """Backward-compatible helper for a single video."""
    item_id = drive_file_id or video_path.name
    item = VideoItem(item_id, video_path, captions)
    results = run_cycle(
        settings, [item], 
        platforms=target_platforms, 
        account_name=account_name, 
        driver=driver,
        gologin_token=gologin_token,
        gologin_profile_id=gologin_profile_id
    )
    return results[item_id]
