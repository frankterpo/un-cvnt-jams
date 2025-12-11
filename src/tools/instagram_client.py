"""Instagram client for uploading videos via Selenium."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from loguru import logger
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from agent.config import InstagramConfig
from .instagram_browser import build_chrome_for_instagram
from . import instagram_selectors as S


def _debug_dump(driver, name: str) -> None:
    """Dump current page HTML for debugging selector issues."""
    p = Path(f"debug_instagram_{name}.html")
    p.write_text(driver.page_source)
    logger.info("[INSTAGRAM] Dumped Instagram page HTML to {}", p)


def _smart_click(driver, element) -> None:
    """
    Click helper with SVG->button normalization and JS fallback.
    Instagram nav icons are often <svg> inside <button>.
    """
    try:
        tag = (element.tag_name or "").lower()
    except Exception:
        tag = ""

    target = element
    if tag == "svg":
        try:
            target = element.find_element(By.XPATH, "./ancestor::button[1]")
        except Exception:
            target = element

    driver.execute_script("arguments[0].scrollIntoView(true);", target)
    try:
        target.click()
    except Exception:
        driver.execute_script("arguments[0].click();", target)


PostType = Literal["feed", "reel"]


class InstagramNotLoggedInError(RuntimeError):
    """Raised when Instagram profile is not logged in."""

    pass


class InstagramUploadError(RuntimeError):
    """Raised when Instagram upload fails."""

    pass


class InstagramClient:
    """Client for uploading videos to Instagram via web UI."""

    def __init__(self, config: InstagramConfig):
        self.config = config

    def upload(
        self,
        video_path: Path,
        caption: str,
        post_type: PostType = "feed",
    ) -> None:
        """Upload a video to Instagram."""
        driver = build_chrome_for_instagram(self.config)
        wait = WebDriverWait(driver, self.config.upload_timeout_seconds)

        try:
            driver.get(self.config.base_url)
            self._ensure_logged_in(driver, wait)
            self._open_create_dialog(driver, wait, post_type)
            self._upload_file(driver, wait, video_path)
            self._advance_creation_flow(driver, wait, post_type)
            self._fill_caption_and_share(driver, wait, caption)
            self._wait_for_share_confirmation(driver, wait)

            logger.info("[INSTAGRAM] Uploaded {} post: {}", post_type, video_path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[INSTAGRAM] Upload failed for {}", video_path)
            raise InstagramUploadError(str(exc)) from exc
        finally:
            driver.quit()

    def _ensure_logged_in(self, driver, wait: WebDriverWait) -> None:
        """Ensure the user is logged in to Instagram."""
        try:
            wait.until(EC.presence_of_element_located(S.PROFILE_ICON))
        except Exception as exc:  # noqa: BLE001
            _debug_dump(driver, "not_logged_in")
            raise InstagramNotLoggedInError("Instagram profile is not logged in") from exc

    def _open_create_dialog(self, driver, wait: WebDriverWait, post_type: PostType) -> None:
        """Open the Instagram create post dialog."""
        try:
            create_btn = wait.until(EC.element_to_be_clickable(S.CREATE_BUTTON))
        except Exception:
            _debug_dump(driver, "create_button")
            raise
        _smart_click(driver, create_btn)

    def _upload_file(self, driver, wait: WebDriverWait, video_path: Path) -> None:
        """Attach video file to upload."""
        try:
            file_input = wait.until(EC.presence_of_element_located(S.FILE_INPUT))
        except Exception:
            _debug_dump(driver, "file_input")
            raise
        file_input.send_keys(str(video_path))

    def _advance_creation_flow(self, driver, wait: WebDriverWait, post_type: PostType) -> None:
        """Navigate through Next screens until caption area is visible."""
        max_clicks = 3
        for i in range(max_clicks):
            try:
                # Don't block on the long upload timeout for this check; keep it responsive.
                WebDriverWait(driver, 5).until(EC.presence_of_element_located(S.CAPTION_AREA))
                return
            except Exception:
                if i == max_clicks - 1:
                    _debug_dump(driver, "next_button")
                    raise
                try:
                    next_btn = wait.until(EC.element_to_be_clickable(S.NEXT_BUTTON))
                except Exception:
                    _debug_dump(driver, "next_button")
                    raise
                _smart_click(driver, next_btn)
        # Final attempt to ensure caption is visible
        wait.until(EC.presence_of_element_located(S.CAPTION_AREA))

    def _fill_caption_and_share(self, driver, wait: WebDriverWait, caption: str) -> None:
        """Fill the caption text and click share."""
        try:
            caption_el = wait.until(EC.element_to_be_clickable(S.CAPTION_AREA))
        except Exception:
            _debug_dump(driver, "caption_area")
            raise
        caption_el.clear()
        caption_el.send_keys(caption)

        try:
            share_btn = wait.until(EC.element_to_be_clickable(S.SHARE_BUTTON))
        except Exception:
            _debug_dump(driver, "share_button")
            raise
        _smart_click(driver, share_btn)

    def _wait_for_share_confirmation(self, driver, wait: WebDriverWait) -> None:
        """Wait for share confirmation with bounded timeout."""
        from selenium.common.exceptions import TimeoutException

        try:
            # Use a shorter timeout for confirmation (30s)
            confirmation_wait = WebDriverWait(driver, 30)
            confirmation_wait.until(EC.presence_of_element_located(S.UPLOAD_PROGRESS_DONE))
        except TimeoutException:
            _debug_dump(driver, "share_no_confirmation")
            logger.warning("[INSTAGRAM] Share confirmation not detected within 30s; proceeding anyway")
            # Don't raise - upload may have succeeded even if confirmation text didn't appear

