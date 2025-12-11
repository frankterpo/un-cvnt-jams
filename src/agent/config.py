"""Configuration models for social media agents."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

# Load .env automatically on import (local dev)
load_dotenv()


class TikTokConfig(BaseModel):
    """Configuration for TikTok uploads."""

    cookies_path: Path
    use_proxy: bool = False
    proxy_host: Optional[str] = None
    proxy_port: Optional[int] = None
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None
    headless: bool = True


class YouTubeConfig(BaseModel):
    """Configuration for YouTube uploads."""

    profile_dir: Path
    upload_url: str = "https://studio.youtube.com"
    headless: bool = True
    upload_timeout_seconds: int = 180


class InstagramConfig(BaseModel):
    """Configuration for Instagram uploads."""

    profile_dir: Path
    base_url: str = "https://www.instagram.com"
    headless: bool = True
    upload_timeout_seconds: int = 180


class Settings(BaseModel):
    """Global settings for the social agent."""

    tiktok: TikTokConfig | None = None
    youtube: YouTubeConfig | None = None
    instagram: InstagramConfig | None = None


def _env_path(name: str) -> Path:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return Path(value).expanduser().resolve()


def load_settings() -> Settings:
    """Build Settings from environment variables (.env for local dev)."""
    try:
        tiktok = TikTokConfig(
            cookies_path=_env_path("TIKTOK_COOKIES_PATH"),
            headless=os.getenv("TIKTOK_HEADLESS", "true").lower() == "true",
        )

        youtube = YouTubeConfig(
            profile_dir=_env_path("YOUTUBE_PROFILE_DIR"),
            upload_url=os.getenv("YOUTUBE_UPLOAD_URL", "https://studio.youtube.com"),
            headless=os.getenv("YOUTUBE_HEADLESS", "true").lower() == "true",
        )

        instagram = InstagramConfig(
            profile_dir=_env_path("INSTAGRAM_PROFILE_DIR"),
            base_url=os.getenv("INSTAGRAM_BASE_URL", "https://www.instagram.com"),
            headless=os.getenv("INSTAGRAM_HEADLESS", "true").lower() == "true",
        )

        return Settings(tiktok=tiktok, youtube=youtube, instagram=instagram)
    except ValidationError as e:
        raise RuntimeError(f"Invalid settings: {e}") from e

