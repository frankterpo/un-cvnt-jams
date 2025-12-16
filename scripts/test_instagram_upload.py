#!/usr/bin/env python3
"""Test script for Instagram uploads.

Usage:
    PYTHONPATH=src python scripts/test_instagram_upload.py \\
      --video /abs/path/to/video.mp4 \\
      --caption "UCJ IG test" \\
      --profile-dir /abs/path/to/chrome-profiles/instagram-main

For headless mode:
    PYTHONPATH=src python scripts/test_instagram_upload.py \\
      --video /abs/path/to/video.mp4 \\
      --caption "UCJ IG test" \\
      --profile-dir /abs/path/to/chrome-profiles/instagram-main \\
      --headless
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent.config import load_settings, InstagramConfig
from loguru import logger
from tools.instagram_client import InstagramClient


def main() -> None:
    """Test Instagram upload."""
    import argparse

    parser = argparse.ArgumentParser(description="Test Instagram upload")
    parser.add_argument("--video", type=Path, required=True, help="Path to video file")
    parser.add_argument("--caption", type=str, default="UCJ Instagram test upload", help="Video caption")
    parser.add_argument("--profile-dir", type=Path, required=True, help="Path to Chrome profile directory")
    parser.add_argument("--post-type", type=str, default="feed", choices=["feed", "reel"], help="Post type")
    parser.add_argument("--headless", action="store_true", help="Override headless to True")
    parser.add_argument("--run-id", type=str, default=None, help="Run identifier for artifact folder naming")
    parser.add_argument("--debug-dir", type=Path, default=None, help="Directory to write run artifacts")
    parser.add_argument("--interactive-login", action="store_true", help="Enable HITL login via CDP+screencast")
    parser.add_argument(
        "--interactive-timeout-secs",
        type=int,
        default=None,
        help="Max seconds to wait for HITL login before failing",
    )
    parser.add_argument("--cdp-port", type=int, default=None, help="CDP port for DevTools screencast")

    args = parser.parse_args()

    video_path = args.video
    if not video_path.exists():
        print(f"Error: Video file not found: {video_path}")
        sys.exit(1)

    profile_dir = args.profile_dir
    if not profile_dir.exists():
        print(f"Error: Profile directory not found: {profile_dir}")
        sys.exit(1)

    # Load settings and override with CLI args
    settings = load_settings()
    if settings.instagram:
        # Override profile_dir and headless from CLI
        settings.instagram.profile_dir = profile_dir
        if args.headless:
            settings.instagram.headless = True
        if args.run_id:
            settings.instagram.run_id = args.run_id
        if args.debug_dir:
            settings.instagram.debug_dir = args.debug_dir
        if args.interactive_login:
            settings.instagram.interactive_login = True
        if args.interactive_timeout_secs is not None:
            settings.instagram.interactive_timeout_secs = args.interactive_timeout_secs
        if args.cdp_port is not None:
            settings.instagram.cdp_port = args.cdp_port
    else:
        # Create new config if not in settings
        settings.instagram = InstagramConfig(
            profile_dir=profile_dir,
            headless=args.headless,
            run_id=args.run_id,
            debug_dir=args.debug_dir,
            interactive_login=args.interactive_login,
            interactive_timeout_secs=args.interactive_timeout_secs or 900,
            cdp_port=args.cdp_port or 9222,
        )

    logger.info(
        "[INSTAGRAM] Resolved config: profile_dir={}, headless={}, base_url={}, run_id={}, debug_dir={}, interactive_login={}, interactive_timeout_secs={}, cdp_port={}",
        settings.instagram.profile_dir,
        settings.instagram.headless,
        settings.instagram.base_url,
        settings.instagram.run_id,
        settings.instagram.debug_dir,
        settings.instagram.interactive_login,
        settings.instagram.interactive_timeout_secs,
        settings.instagram.cdp_port,
    )

    # Upload
    try:
        print(f"Uploading {video_path} to Instagram ({args.post_type})...")
        client = InstagramClient(settings.instagram)
        client.upload(video_path, args.caption, post_type=args.post_type)
        print("✅ Upload successful!")
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
