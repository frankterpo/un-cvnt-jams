#!/usr/bin/env python3
"""Test script for YouTube uploads."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent.config import Settings, YouTubeConfig
from tools.youtube_client import YouTubeClient
from tools.youtube_metadata import YouTubeMetadata


def main() -> None:
    """Test YouTube upload."""
    import argparse

    parser = argparse.ArgumentParser(description="Test YouTube upload")
    parser.add_argument("--video", required=True, help="Path to video file")
    parser.add_argument("--title", required=True, help="Video title")
    parser.add_argument("--description", default="", help="Video description")
    parser.add_argument("--tags", help="Comma-separated tags")
    parser.add_argument("--profile-dir", required=True, help="Path to Chrome profile directory")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")

    args = parser.parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"Error: Video file not found: {video_path}")
        sys.exit(1)

    profile_dir = Path(args.profile_dir)
    if not profile_dir.exists():
        print(f"Error: Profile directory not found: {profile_dir}")
        sys.exit(1)

    # Create config
    youtube_config = YouTubeConfig(
        profile_dir=profile_dir,
        headless=args.headless,
    )

    settings = Settings(youtube=youtube_config)

    # Create metadata
    tags = args.tags.split(",") if args.tags else []
    meta = YouTubeMetadata(
        title=args.title,
        description=args.description,
        tags=tags,
    )

    # Upload
    try:
        print(f"Uploading {video_path} to YouTube...")
        client = YouTubeClient(settings.youtube)
        video_id = client.upload_video(video_path, meta)
        print(f"✅ Upload successful! Video ID: {video_id}")
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

