#!/usr/bin/env python3
"""CLI entrypoint for the social media upload agent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from loguru import logger

from agent.config import load_settings
from agent.workflow import VideoItem, run_cycle


def main() -> None:
    parser = argparse.ArgumentParser(description="Social agent CLI")
    parser.add_argument(
        "--video",
        type=Path,
        required=True,
        help="Path to a local video file",
    )
    parser.add_argument(
        "--meta",
        type=Path,
        required=False,
        help="JSON file with captions/metadata per platform",
    )
    parser.add_argument(
        "--platforms",
        type=str,
        default="tiktok,youtube,instagram",
        help="Comma-separated list of platforms",
    )
    parser.add_argument(
        "--id",
        type=str,
        default="local-test",
        help="Stable id for idempotency (e.g. drive file id)",
    )

    args = parser.parse_args()

    if not args.video.exists():
        raise SystemExit(f"Video file not found: {args.video}")

    if args.meta and not args.meta.exists():
        raise SystemExit(f"Meta JSON file not found: {args.meta}")

    settings = load_settings()
    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]

    if args.meta:
        captions = json.loads(args.meta.read_text())
    else:
        captions = {
            "tiktok": "Test TikTok upload",
            "youtube": {
                "title": "Test YouTube upload",
                "description": "Uploaded by social-agent",
                "tags": [],
            },
            "instagram": "Test Instagram upload",
        }

    item = VideoItem(id=args.id, path=args.video, captions=captions)

    logger.info("Running agent for {}, platforms={}", args.video, platforms)
    results = run_cycle(settings, [item], platforms)

    item_results = results.get(item.id, {})
    for platform, result in item_results.items():
        status = result.get("status")
        if status == "success":
            logger.success("{}: success", platform)
            if "video_id" in result:
                logger.info("  video_id={}", result["video_id"])
        elif status == "skipped":
            logger.info("{}: skipped ({})", platform, result.get("reason"))
        else:
            logger.error("{}: failed - {}", platform, result.get("error"))

    # Exit non-zero if any platform failed
    if any(r.get("status") == "failed" for r in item_results.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

