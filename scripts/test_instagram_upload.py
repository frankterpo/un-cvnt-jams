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
    else:
        # Create new config if not in settings
        settings.instagram = InstagramConfig(
            profile_dir=profile_dir,
            headless=args.headless,
        )

    logger.info(
        "[INSTAGRAM] Resolved config: profile_dir={}, headless={}, base_url={}",
        settings.instagram.profile_dir,
        settings.instagram.headless,
        settings.instagram.base_url,
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

