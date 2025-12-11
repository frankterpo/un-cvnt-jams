"""TikTok client wrapper around tiktok-uploader.

We run TikTok uploads through `tiktok-uploader`, but we own the Selenium
WebDriver lifecycle so we can emit robust HTML debug dumps (parity with
YouTube/Instagram flows).
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Iterable

from loguru import logger
from tiktok_uploader import config as tt_config
from tiktok_uploader.types import ProxyDict
from tiktok_uploader.upload import upload_videos

from agent.config import TikTokConfig
from .tiktok_auth import build_auth
from .tiktok_browser import build_chrome_for_tiktok


class TikTokUploadError(RuntimeError):
    """Raised when TikTok upload fails."""

    pass


def _debug_dump(driver, name: str) -> None:
    """Dump current page HTML for debugging selector/auth issues."""
    p = Path(f"debug_tiktok_{name}.html")
    try:
        p.write_text(driver.page_source)
        logger.info("[TIKTOK] Dumped TikTok page HTML to {}", p)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[TIKTOK] Failed to write debug dump {}: {}", p, exc)


def _parse_schedule_time(raw: str | None) -> datetime.datetime | None:
    if not raw:
        return None
    # Accept common ISO-8601 strings; if naive assume UTC.
    dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def _proxy_from_config(config: TikTokConfig) -> ProxyDict | None:
    if not getattr(config, "use_proxy", False):
        return None
    if not config.proxy_host or not config.proxy_port:
        return None
    proxy: ProxyDict = {
        "host": str(config.proxy_host),
        "port": str(config.proxy_port),
    }
    if config.proxy_username:
        proxy["user"] = str(config.proxy_username)
    if config.proxy_password:
        proxy["password"] = str(config.proxy_password)
    return proxy


class TikTokClient:
    """Thin wrapper around `tiktok-uploader` for the social agent."""

    def __init__(self, config: TikTokConfig):
        self.config = config
        self.auth = build_auth(config)

    def upload_single(
        self,
        video_path: Path,
        description: str,
        *,
        allow_comments: bool = True,
        allow_duet: bool = True,
        allow_stitch: bool = True,
        schedule_time: str | None = None,
    ) -> None:
        """Upload a single video to TikTok."""
        driver = build_chrome_for_tiktok(self.config)
        prev_quit_on_end = getattr(tt_config, "quit_on_end", True)
        tt_config.quit_on_end = False  # we own driver lifecycle for dumps
        try:
            logger.info("[TIKTOK] Starting upload: {}", video_path)

            # Preflight auth dump: helps debug cookie issues fast.
            try:
                self.auth.authenticate_agent(driver)
                _debug_dump(driver, "pre_upload")
            except Exception:
                _debug_dump(driver, "auth_failed")
                raise

            schedule_dt = _parse_schedule_time(schedule_time)
            proxy = _proxy_from_config(self.config)

            def _on_complete(_video_dict) -> None:
                # Best-effort snapshot after each attempt; useful even on "soft failures"
                # where tiktok-uploader catches the exception and returns a failed list.
                _debug_dump(driver, "post_attempt")

            failed = upload_videos(
                videos=[
                    {
                        "path": str(video_path),
                        "description": description,
                        **({"schedule": schedule_dt} if schedule_dt else {}),
                    }
                ],
                auth=self.auth,
                proxy=proxy,
                browser_agent=driver,
                headless=self.config.headless,
                num_retries=2,
                on_complete=_on_complete,
                comment=allow_comments,
                duet=allow_duet,
                stitch=allow_stitch,
            )

            if failed:
                _debug_dump(driver, "failed")
                raise TikTokUploadError(f"TikTok upload failed (failed={failed})")

            _debug_dump(driver, "success")
            logger.info("[TIKTOK] Upload succeeded: {}", video_path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[TIKTOK] Upload failed: {}", video_path)
            try:
                _debug_dump(driver, "exception")
            except Exception:
                pass
            raise TikTokUploadError(str(exc)) from exc
        finally:
            tt_config.quit_on_end = prev_quit_on_end
            try:
                driver.quit()
            except Exception:
                pass

    def upload_batch(
        self,
        items: Iterable[tuple[Path, str]],
    ) -> None:
        """Upload multiple videos to TikTok."""
        driver = build_chrome_for_tiktok(self.config)
        prev_quit_on_end = getattr(tt_config, "quit_on_end", True)
        tt_config.quit_on_end = False
        try:
            videos = [{"path": str(p), "description": d} for p, d in items]
            logger.info("[TIKTOK] Starting batch upload: {} videos", len(videos))

            self.auth.authenticate_agent(driver)
            _debug_dump(driver, "pre_upload_batch")

            proxy = _proxy_from_config(self.config)

            def _on_complete(_video_dict) -> None:
                _debug_dump(driver, "post_attempt_batch")

            failed = upload_videos(
                videos=videos,
                auth=self.auth,
                proxy=proxy,
                browser_agent=driver,
                headless=self.config.headless,
                num_retries=2,
                on_complete=_on_complete,
            )

            if failed:
                _debug_dump(driver, "failed_batch")
                raise TikTokUploadError(f"TikTok batch upload failed (failed={failed})")

            _debug_dump(driver, "success_batch")
            logger.info("[TIKTOK] Batch upload succeeded: {} videos", len(videos))
        except Exception as exc:  # noqa: BLE001
            logger.exception("[TIKTOK] Batch upload failed")
            try:
                _debug_dump(driver, "exception_batch")
            except Exception:
                pass
            raise TikTokUploadError(str(exc)) from exc
        finally:
            tt_config.quit_on_end = prev_quit_on_end
            try:
                driver.quit()
            except Exception:
                pass

