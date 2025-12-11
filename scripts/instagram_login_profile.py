#!/usr/bin/env python3
"""Script to create a logged-in Instagram Chrome profile."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent.config import InstagramConfig
from tools.instagram_browser import build_chrome_for_instagram


def main() -> None:
    """Create Instagram login profile."""
    import argparse

    parser = argparse.ArgumentParser(description="Create Instagram login profile")
    parser.add_argument(
        "--profile-dir",
        type=Path,
        required=True,
        help="Path to Chrome profile directory",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode (not recommended for first login)",
    )

    args = parser.parse_args()

    args.profile_dir.mkdir(parents=True, exist_ok=True)

    print(f"Opening Chrome with profile: {args.profile_dir}")
    print("Please log in to Instagram and complete any 2FA.")
    print("Press Enter here once you're logged in and see the Instagram home page...")

    config = InstagramConfig(
        profile_dir=args.profile_dir,
        headless=args.headless,
    )
    driver = build_chrome_for_instagram(config)
    driver.get("https://www.instagram.com/accounts/login/")

    input("Press Enter once logged in...")

    driver.quit()
    print(f"✅ Profile saved to: {args.profile_dir}")
    print("You can now use this profile_dir in your InstagramConfig.")


if __name__ == "__main__":
    main()

