#!/usr/bin/env python3
"""Script to create a logged-in YouTube Chrome profile."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tools.youtube_browser import build_chrome_for_youtube


def main() -> None:
    """Create YouTube login profile."""
    import argparse

    parser = argparse.ArgumentParser(description="Create YouTube login profile")
    parser.add_argument(
        "--profile-dir",
        default="profiles/youtube-main",
        help="Path to Chrome profile directory",
    )

    args = parser.parse_args()

    profile_dir = Path(args.profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)

    print(f"Opening Chrome with profile: {profile_dir}")
    print("Please log in to YouTube Studio and select your channel.")
    print("Press Enter here once you're logged in and see YouTube Studio...")

    driver = build_chrome_for_youtube(profile_dir, headless=False)
    driver.get("https://studio.youtube.com")

    input("Press Enter once logged in...")

    driver.quit()
    print(f"✅ Profile saved to: {profile_dir}")
    print("You can now use this profile_dir in your YouTubeConfig.")


if __name__ == "__main__":
    main()

