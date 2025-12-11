"""Minimal sanity check for configuration loading."""

from __future__ import annotations

from agent.config import load_settings


def main() -> None:
    settings = load_settings()
    print("TikTok cookies:", settings.tiktok.cookies_path)
    print("YouTube profile:", settings.youtube.profile_dir)
    print("Instagram profile:", settings.instagram.profile_dir)


if __name__ == "__main__":
    main()

