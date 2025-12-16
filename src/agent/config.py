"""Configuration models for social media agents."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Dict

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
    headless: bool = False
    upload_timeout_seconds: int = 180
    run_id: str | None = None
    debug_dir: Path | None = None
    interactive_login: bool = False
    interactive_timeout_secs: int = 900
    cdp_port: int = 9222


class GoLoginConfig(BaseModel):
    """Configuration for GoLogin browser automation."""
    
    token: str
    account_email: str  # For profile mapping
    profiles: Dict[str, str] = {}  # profile_name -> profile_id
    headless: bool = False
    timeout_seconds: int = 300

class Settings(BaseModel):
    """Global settings for the social agent."""

    tiktok: Optional[TikTokConfig] = None
    youtube: Optional[YouTubeConfig] = None
    instagram: Optional[InstagramConfig] = None
    gologin_accounts: Dict[str, GoLoginConfig] = {}  # email -> config
    max_novnc_concurrent_sessions: int = 5

    def get_gologin_credentials(self, account_name: str) -> Optional[tuple[str, str]]:
        """
        Find (token, profile_id) for a named social account.
        Returns None if not configured.
        """
        for config in self.gologin_accounts.values():
            if account_name in config.profiles:
                return config.token, config.profiles[account_name]
        return None


def _env_path(name: str) -> Path:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return Path(value).expanduser().resolve()

def _env_optional_path(name: str) -> Path | None:
    value = os.environ.get(name)
    if not value:
        return None
    return Path(value).expanduser().resolve()

def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() == "true"


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
            headless=_env_bool("INSTAGRAM_HEADLESS", default=False),
            run_id=os.getenv("IG_RUN_ID"),
            debug_dir=_env_optional_path("IG_DEBUG_DIR"),
            interactive_login=_env_bool("IG_INTERACTIVE_LOGIN", default=False),
            interactive_timeout_secs=int(os.getenv("IG_INTERACTIVE_TIMEOUT_SECS", "900")),
            cdp_port=int(os.getenv("IG_CDP_PORT", "9222")),
        )

        # Load GoLogin accounts
        gologin_accounts = {}
        
        # Account 1: frankpablote@gmail.com
        token1 = os.getenv("GOLOGIN_TOKEN_1")
        if token1:
            profiles1 = {
                "viixenviices": os.getenv("GOLOGIN_PROFILE_VIIXENVIICES"),
                "popmessparis": os.getenv("GOLOGIN_PROFILE_POPMESSPARIS"),
                "halohavok": os.getenv("GOLOGIN_PROFILE_HALOHAVOK"),
            }
            gologin_accounts["frankpablote@gmail.com"] = GoLoginConfig(
                token=token1,
                account_email="frankpablote@gmail.com",
                profiles={k: v for k, v in profiles1.items() if v}
            )
        
        # Account 2: frankpablote@mac.com  
        token2 = os.getenv("GOLOGIN_TOKEN_2")
        if token2:
            profiles2 = {
                "cigsntofu": os.getenv("GOLOGIN_PROFILE_CIGSNTOFU"),
                "lavenderliqour": os.getenv("GOLOGIN_PROFILE_LAVENDERLIQOUR"),
                "hotcaviarx": os.getenv("GOLOGIN_PROFILE_HOTCAVIARX"),
            }
            gologin_accounts["frankpablote@mac.com"] = GoLoginConfig(
                token=token2,
                account_email="frankpablote@mac.com", 
                profiles={k: v for k, v in profiles2.items() if v}
            )
        
        return Settings(
            tiktok=tiktok,
            youtube=youtube,
            instagram=instagram,
            gologin_accounts=gologin_accounts,
            max_novnc_concurrent_sessions=int(os.getenv("MAX_NOVNC_CONCURRENT_SESSIONS", "5"))
        )
    except ValidationError as e:
        raise RuntimeError(f"Invalid settings: {e}") from e
