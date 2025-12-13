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
from tiktok_uploader import upload as tt_upload
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


def _dismiss_cookie_banner(driver) -> None:
    """
    TikTok shows a bottom cookie banner (`div.tiktok-cookie-banner`) and a toast
    (`.cookie-banner-toast`). The default tiktok-uploader selector targets a
    custom tag and misses this variant, so we proactively remove both.
    """
    try:
        driver.execute_script(
            """
            document.querySelectorAll('div.tiktok-cookie-banner, .cookie-banner-toast')
                    .forEach(el => el.remove());
            """
        )
    except Exception:
        pass


def _dismiss_tutorial_overlay(driver) -> None:
    """
    Remove TikTok's tutorial/joyride overlay that blocks clicks on inputs.
    Observed selector: .react-joyride__overlay (role=presentation, high z-index).
    """
    try:
        driver.execute_script(
            """
            document.querySelectorAll('.react-joyride__overlay, [data-test-id="overlay"]')
                    .forEach(el => el.remove());
            """
        )
    except Exception:
        pass


def _monkeypatch_uploader_cookie_banner() -> None:
    """
    tiktok-uploader's _remove_cookies_window expects a custom tag; on current
    pages it raises NoSuchElement. Override it to a no-op and rely on our
    _dismiss_cookie_banner instead.
    """
    try:
        tt_upload._remove_cookies_window = lambda driver: None  # type: ignore
    except Exception:
        pass


_orig_set_description = getattr(tt_upload, "_set_description", None)
_orig_set_interactivity = getattr(tt_upload, "_set_interactivity", None)


def _patch_tutorial_overlay() -> None:
    """
    Wrap tiktok-uploader's _set_description and _set_interactivity to dismiss
    the joyride overlay before interacting with fields.
    """
    if _orig_set_description:

        def _wrapped_set_description(driver, description: str, *args, **kwargs):
            _dismiss_tutorial_overlay(driver)
            return _orig_set_description(driver, description, *args, **kwargs)

        tt_upload._set_description = _wrapped_set_description  # type: ignore

    if _orig_set_interactivity:

        def _wrapped_set_interactivity(driver, *args, **kwargs):
            _dismiss_tutorial_overlay(driver)
            return _orig_set_interactivity(driver, *args, **kwargs)

        tt_upload._set_interactivity = _wrapped_set_interactivity  # type: ignore


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
        driver=None,
    ) -> None:
        """Upload a single video to TikTok."""
        
        should_quit = False
        if not driver:
            driver = build_chrome_for_tiktok(self.config)
            should_quit = True

        prev_quit_on_end = getattr(tt_config, "quit_on_end", True)
        tt_config.quit_on_end = False  # we own driver lifecycle for dumps
        try:
            _monkeypatch_uploader_cookie_banner()
            _patch_tutorial_overlay()
            logger.info("[TIKTOK] Starting upload: {}", video_path)

            # Preflight auth dump: helps debug cookie issues fast.
            try:
                self.auth.authenticate_agent(driver)
                _dismiss_cookie_banner(driver)
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
                skip_split_window=True,  # avoid split window click path
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
            if should_quit:
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
                skip_split_window=True,
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

