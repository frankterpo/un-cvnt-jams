#!/usr/bin/env python3
"""Test script for TikTok uploads.

Usage:
    PYTHONPATH=src python scripts/test_tiktok_upload.py \\
      --video /abs/path/to/video.mp4 \\
      --caption "UCJ TikTok test"

For headless mode:
    PYTHONPATH=src python scripts/test_tiktok_upload.py \\
      --video /abs/path/to/video.mp4 \\
      --caption "UCJ TikTok test" \\
      --headless
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent.config import load_settings, TikTokConfig
from loguru import logger
from tools.tiktok_client import TikTokClient


def main() -> None:
    """Test TikTok upload."""
    import argparse

    parser = argparse.ArgumentParser(description="Test TikTok upload")
    parser.add_argument("--video", type=Path, required=True, help="Path to video file")
    parser.add_argument("--caption", type=str, default="UCJ TikTok test upload", help="Video caption")
    parser.add_argument("--headless", action="store_true", help="Override headless to True")

    args = parser.parse_args()

    video_path = args.video
    if not video_path.exists():
        print(f"Error: Video file not found: {video_path}")
        sys.exit(1)

    # Load settings and override headless if specified
    settings = load_settings()
    if not settings.tiktok:
        raise ValueError("TikTok config not found in settings. Ensure TIKTOK_COOKIES_PATH is set in .env")

    logger.info(
        "[TIKTOK] Resolved config: cookies_path={}, headless={}",
        settings.tiktok.cookies_path,
        settings.tiktok.headless,
    )

    if args.headless:
        # Create new config with headless override if config is immutable
        settings.tiktok = TikTokConfig(
            cookies_path=settings.tiktok.cookies_path,
            headless=True,
            use_proxy=settings.tiktok.use_proxy,
            proxy_host=settings.tiktok.proxy_host,
            proxy_port=settings.tiktok.proxy_port,
            proxy_username=settings.tiktok.proxy_username,
            proxy_password=settings.tiktok.proxy_password,
        )

    # Upload
    try:
        print(f"Uploading {video_path} to TikTok...")
        client = TikTokClient(settings.tiktok)
        client.upload_single(video_path, args.caption)
        print("✅ Upload successful!")
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

