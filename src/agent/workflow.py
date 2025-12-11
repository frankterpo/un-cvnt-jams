"""Workflow integration for social media uploads with idempotency."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from loguru import logger

from agent.config import Settings
from agent.state import UploadState
from tools.tiktok_client import TikTokClient
from tools.youtube_client import YouTubeClient
from tools.youtube_metadata import YouTubeMetadata
from tools.instagram_client import InstagramClient


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


def _publish_tiktok(settings: Settings, state: UploadState, item: VideoItem) -> dict:
    platform = "tiktok"
    if state.has_success(item.id, platform):
        logger.info("[TIKTOK] Skipping {} – already uploaded", item.id)
        return {"status": "skipped", "reason": "already_uploaded"}

    caption = item.captions.get("tiktok")
    if not caption:
        logger.info("[TIKTOK] No caption for {}, skipping", item.id)
        return {"status": "skipped", "reason": "missing_caption"}

    client = TikTokClient(settings.tiktok)
    try:
        client.upload_single(item.path, caption)
        state.mark_success(item.id, platform)
        return {"status": "success"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("[TIKTOK] Upload failed for {}", item.id)
        state.mark_failed(item.id, platform)
        return {"status": "failed", "error": str(exc)}


def _publish_youtube(settings: Settings, state: UploadState, item: VideoItem) -> dict:
    platform = "youtube"
    if state.has_success(item.id, platform):
        logger.info("[YOUTUBE] Skipping {} – already uploaded", item.id)
        return {"status": "skipped", "reason": "already_uploaded"}

    ydata = item.captions.get("youtube")
    if not ydata:
        logger.info("[YOUTUBE] No metadata for {}, skipping", item.id)
        return {"status": "skipped", "reason": "missing_metadata"}

    meta = YouTubeMetadata(
        title=ydata["title"],
        description=ydata["description"],
        tags=ydata.get("tags", []),
        publish_at=_parse_publish_at(ydata.get("publish_at")),
    )

    client = YouTubeClient(settings.youtube)
    try:
        video_id = client.upload_video(item.path, meta)
        state.mark_success(item.id, platform)
        return {"status": "success", "video_id": video_id}
    except Exception as exc:  # noqa: BLE001
        logger.exception("[YOUTUBE] Upload failed for {}", item.id)
        state.mark_failed(item.id, platform)
        return {"status": "failed", "error": str(exc)}


def _publish_instagram(settings: Settings, state: UploadState, item: VideoItem) -> dict:
    platform = "instagram"
    if state.has_success(item.id, platform):
        logger.info("[INSTAGRAM] Skipping {} – already uploaded", item.id)
        return {"status": "skipped", "reason": "already_uploaded"}

    caption = item.captions.get("instagram")
    if not caption:
        logger.info("[INSTAGRAM] No caption for {}, skipping", item.id)
        return {"status": "skipped", "reason": "missing_caption"}

    client = InstagramClient(settings.instagram)
    try:
        client.upload(item.path, caption, post_type="feed")
        state.mark_success(item.id, platform)
        return {"status": "success"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("[INSTAGRAM] Upload failed for {}", item.id)
        state.mark_failed(item.id, platform)
        return {"status": "failed", "error": str(exc)}


def run_cycle(
    settings: Settings,
    items: Iterable[VideoItem],
    platforms: list[str] | None = None,
) -> dict[str, dict[str, dict]]:
    """
    Iterate over video items and post to selected platforms with idempotency.

    Returns a mapping: {item.id: {platform: {status,...}}}
    """
    platforms = platforms or ["tiktok", "youtube", "instagram"]
    state = UploadState.load_default()
    all_results: dict[str, dict[str, dict]] = {}

    for item in items:
        item_results: dict[str, dict] = {}
        logger.info("[WORKFLOW] Processing item {} ({})", item.id, item.path)

        if "tiktok" in platforms:
            item_results["tiktok"] = _publish_tiktok(settings, state, item)

        if "youtube" in platforms:
            item_results["youtube"] = _publish_youtube(settings, state, item)

        if "instagram" in platforms:
            item_results["instagram"] = _publish_instagram(settings, state, item)

        all_results[item.id] = item_results

    state.save()
    return all_results


def run_cycle_single(
    settings: Settings,
    video_path: Path,
    captions: dict,
    target_platforms: list[str] | None = None,
    drive_file_id: str | None = None,
) -> dict[str, dict]:
    """Backward-compatible helper for a single video."""
    item_id = drive_file_id or video_path.name
    item = VideoItem(item_id, video_path, captions)
    results = run_cycle(settings, [item], platforms=target_platforms)
    return results[item_id]

