"""YouTube client for uploading videos via Selenium."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
import os
import re
from urllib.parse import urlparse, parse_qs
import time

from loguru import logger
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from agent.config import YouTubeConfig
from .youtube_browser import build_chrome_for_youtube
from .youtube_metadata import YouTubeMetadata
from . import youtube_selectors as S


def _debug_dump(driver, name: str) -> None:
    """Dump current page HTML for debugging selector issues."""
    p = Path(f"debug_{name}.html")
    p.write_text(driver.page_source)
    logger.info("[YOUTUBE] Dumped YouTube page HTML to {}", p)


def _extract_video_id_from_url(url: str) -> str | None:
    """
    Extract video id from common YouTube Studio / watch URLs.
    Supports:
    - https://studio.youtube.com/video/<VIDEO_ID>/edit
    - https://studio.youtube.com/video/<VIDEO_ID>/upload
    - https://www.youtube.com/watch?v=<VIDEO_ID>&...
    """
    parsed = urlparse(url)

    # Studio pattern: /video/<id>/...
    m = re.search(r"/video/([A-Za-z0-9_-]{6,})/", parsed.path)
    if m:
        return m.group(1)

    # Watch pattern: ?v=<id>
    qs = parse_qs(parsed.query)
    if "v" in qs and qs["v"]:
        return qs["v"][0]

    logger.warning("[YOUTUBE] Could not extract video ID from URL: {}", url)
    return None


class YouTubeUploadError(RuntimeError):
    """Raised when YouTube upload fails."""

    pass


class YouTubeClient:
    """Client for uploading videos to YouTube via Studio."""

    def __init__(self, config: YouTubeConfig):
        self.config = config

    def upload_video(self, video_path: Path, meta: YouTubeMetadata, driver=None) -> str:
        """Upload a video to YouTube and return the video ID."""
        
        # If driver is provided, use it (and don't close it). 
        # Otherwise create one and manage lifecycle.
        should_quit = False
        if not driver:
            driver = build_chrome_for_youtube(self.config.profile_dir, self.config.headless)
            should_quit = True
            
        wait = WebDriverWait(driver, self.config.upload_timeout_seconds)

        try:
            driver.get(self.config.upload_url)

            # 1. Open upload dialog
            self._open_upload_dialog(driver, wait)

            # 2. Upload file
            self._attach_video_file(wait, video_path)

            # 3. Fill metadata
            self._fill_metadata(driver, wait, meta)

            # 4. Advance through Checks to Visibility
            self._advance_to_visibility(driver, wait)

            # 5. Visibility / scheduling
            video_id = self._set_visibility_and_finish(driver, wait, meta)

            logger.info("[YOUTUBE] Uploaded video: {} as id {}", video_path, video_id)
            return video_id
        except Exception as exc:  # noqa: BLE001
            logger.exception("[YOUTUBE] Upload failed for {}", video_path)
            raise YouTubeUploadError(str(exc)) from exc
        finally:
            if should_quit:
                driver.quit()

    def _safe_click(self, driver, element, timeout: float = 2.0):
        """
        Attempt to click an element. If intercepted, try JS click.
        """
        try:
            element.click()
        except Exception as e:
            logger.warning(f"[YOUTUBE] Click intercepted or failed, trying JS click: {e}")
            driver.execute_script("arguments[0].click();", element)

    def _open_upload_dialog(self, driver, wait: WebDriverWait) -> None:
        """Open the YouTube Studio upload dialog."""
        # 1) Click Create button
        try:
            create_btn = wait.until(EC.element_to_be_clickable(S.CREATE_BUTTON))
        except Exception:
            _debug_dump(driver, "yt_create_button")
            raise
        self._safe_click(driver, create_btn)

        # 2) Click "Upload videos" menu item
        try:
            upload_item = wait.until(EC.element_to_be_clickable(S.UPLOAD_MENU_ITEM))
        except Exception:
            _debug_dump(driver, "yt_upload_menu")
            raise
        self._safe_click(driver, upload_item)

    def _attach_video_file(self, wait: WebDriverWait, video_path: Path) -> None:
        """Attach video file to upload."""
        file_input = wait.until(EC.presence_of_element_located(S.FILE_INPUT))
        file_input.send_keys(str(video_path))

    def _fill_metadata(self, driver, wait: WebDriverWait, meta: YouTubeMetadata) -> None:
        """Fill title, description, and tags."""
        # Fill title
        title_input = wait.until(EC.presence_of_element_located(S.TITLE_INPUT))
        title_input.clear()
        title_input.send_keys(meta.title)

        # Fill description
        desc_input = wait.until(EC.presence_of_element_located(S.DESCRIPTION_INPUT))
        desc_input.clear()
        desc_input.send_keys(meta.description)

        # Set "Not for kids"
        # Wait for potential scrims to fade (simple sleep is sometimes safest for animations)
        time.sleep(1.0)
        not_for_kids = wait.until(EC.element_to_be_clickable(S.NOT_FOR_KIDS_RADIO))
        
        # Scroll to view to minimize overlay issues
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", not_for_kids)
        time.sleep(0.5)
        
        self._safe_click(driver, not_for_kids)

        # Click Next to proceed
        self._click_next(driver, wait)

    def _click_next(self, driver, wait: WebDriverWait) -> None:
        """Click the generic Next button in the upload wizard."""
        try:
            next_btn = wait.until(EC.element_to_be_clickable(S.NEXT_BUTTON))
        except TimeoutException:
            _debug_dump(driver, "yt_next_button")
            raise
        
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
        time.sleep(0.5)
        self._safe_click(driver, next_btn)

    def _advance_to_visibility(self, driver, wait: WebDriverWait) -> None:
        """
        Move from Details -> Checks -> Visibility by clicking Next twice.
        If any step fails to expose Next, dump page for debugging.
        """
        try:
            self._click_next(driver, wait)  # Details -> Checks
            time.sleep(1.0) # buffer for transition
            self._click_next(driver, wait)  # Checks -> Visibility
        except Exception:
            _debug_dump(driver, "yt_advance_to_visibility")
            raise

    def _set_visibility_and_finish(self, driver, wait: WebDriverWait, meta: YouTubeMetadata) -> str:
        """Set visibility and finish upload, return video ID."""
        if meta.publish_at:
            # Schedule publication
            schedule_radio = wait.until(EC.element_to_be_clickable(S.SCHEDULE_RADIO))
            self._safe_click(driver, schedule_radio)

            # Set date and time
            date_input = wait.until(EC.presence_of_element_located(S.SCHEDULE_DATE_INPUT))
            time_input = wait.until(EC.presence_of_element_located(S.SCHEDULE_TIME_INPUT))

            # Format datetime for inputs
            publish_date = meta.publish_at.strftime("%Y-%m-%d")
            publish_time = meta.publish_at.strftime("%H:%M")

            date_input.send_keys(publish_date)
            time_input.send_keys(publish_time)
        else:
            # Publish immediately
            public_radio = wait.until(EC.element_to_be_clickable(S.PUBLIC_RADIO))
            self._safe_click(driver, public_radio)

        # Wait until Done/Publish is truly enabled (checks/processing gate this)
        done_timeout = int(os.getenv("YOUTUBE_DONE_TIMEOUT_SECONDS", "300"))
        done_btn = self._wait_for_done_enabled(driver, wait, timeout=done_timeout, poll_seconds=5)

        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", done_btn)
        time.sleep(0.5)
        self._safe_click(driver, done_btn)

        # Wait for navigation that contains the video id and extract it
        wait.until(lambda d: "video/" in d.current_url or "watch?v=" in d.current_url)
        current_url = driver.current_url
        video_id = _extract_video_id_from_url(current_url) or ""
        logger.info("[YOUTUBE] Final Studio URL: {}, parsed video id: {}", current_url, video_id)
        return video_id

    def _wait_for_done_enabled(self, driver, wait: WebDriverWait, timeout: int = 300, poll_seconds: int = 5):
        """
        Wait until the Done/Publish button becomes enabled (aria-disabled not true).
        YouTube keeps it disabled while processing/checks run.
        """
        end = time.time() + timeout
        last_btn = None
        while time.time() < end:
            try:
                # Re-locate element to avoid stale reference
                btn = wait.until(EC.presence_of_element_located(S.DONE_BUTTON))
                last_btn = btn
                disabled = btn.get_attribute("aria-disabled")
                # Also check standard 'disabled' property just in case
                is_disabled_prop = driver.execute_script("return arguments[0].disabled;", btn)
                
                if disabled not in ("true", "True", "1") and not is_disabled_prop:
                    return btn
            except Exception:
                pass
            time.sleep(poll_seconds)
        if last_btn is not None:
            _debug_dump(driver, "yt_done_disabled")
        raise TimeoutException("Done/Publish button stayed disabled")

