"""TikTok authentication helper using cookies."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from tiktok_uploader.auth import AuthBackend

from agent.config import TikTokConfig


class TikTokCookiesMissingError(FileNotFoundError):
    """Raised when TikTok cookies file is not found."""

    pass


def build_auth(config: TikTokConfig) -> AuthBackend:
    """Build TikTok AuthBackend from config.
    
    Note: Cookie parsing is handled by tiktok-uploader's AuthBackend.
    If cookies are malformed, AuthBackend will raise an exception during upload.
    """
    cookies_path = config.cookies_path.expanduser().resolve()
    if not cookies_path.is_file():
        logger.error("TikTok cookies file not found: {}", cookies_path)
        raise TikTokCookiesMissingError(f"TikTok cookies file not found: {cookies_path}")
    logger.debug("Loading TikTok cookies from: {}", cookies_path)
    return AuthBackend(cookies=str(cookies_path))

