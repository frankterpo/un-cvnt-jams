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


def _click_button_by_text(driver, button_text: str, timeout: int = 5) -> bool:
    """
    Smart button clicker that finds buttons by text content.
    Returns True if successfully clicked, False otherwise.
    """
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By

    wait = WebDriverWait(driver, timeout)
    logger.info("[INSTAGRAM] Looking for '{}' button", button_text)

    # Try XPath selectors first - prioritize role="button" elements
    # For Share button, be very specific to avoid other "Share" elements
    if button_text == "Share":
        selectors = [
            f"//div[contains(@class, 'x1i10hfl') and contains(@class, 'x1qjc9v5') and text()='{button_text}']",
            f"//div[@role='button' and contains(@class, 'x1i10hfl') and text()='{button_text}']",
            f"//div[contains(@class, 'x1i10hfl') and text()='{button_text}']",
            f"//*[@role='button' and normalize-space()='{button_text}']",
            f"//button[normalize-space()='{button_text}']",
        ]
    else:
        selectors = [
            f"//*[@role='button' and normalize-space()='{button_text}']",
            f"//button[normalize-space()='{button_text}']",
            f"//div[normalize-space()='{button_text}']",
            f"//span[normalize-space()='{button_text}']",
            f"//*[text()='{button_text}' and @role='button']",
        ]

    for selector in selectors:
        try:
            button = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
            _smart_click(driver, button)
            logger.info("[INSTAGRAM] Successfully clicked '{}' button with selector: {}", button_text, selector)
            return True
        except Exception:
            continue

    # JavaScript fallback - more targeted
    try:
        result = driver.execute_script(f"""
            // Look for elements with role="button" first, then any element with the text
            const elements = [
                ...document.querySelectorAll('[role="button"]'),
                ...document.querySelectorAll('div.x1i10hfl'),
                ...document.querySelectorAll('div, span, button')
            ].filter(el => {{
                const text = (el.textContent || el.innerText || '').trim();
                return text === '{button_text}' || text.toLowerCase() === '{button_text}'.toLowerCase();
            }});

            console.log('Found', elements.length, 'potential {button_text} elements');

            for (let i = 0; i < elements.length; i++) {{
                const el = elements[i];
                console.log('Trying element', i, ':', el, 'text:', el.textContent);
                try {{
                    el.click();
                    console.log('Successfully clicked {button_text} button');
                    return true;
                }} catch (e) {{
                    console.log('Click failed for element', i, e.message);
                }}
            }}
            return false;
        """)

        if result:
            logger.info("[INSTAGRAM] JavaScript fallback clicked '{}' button", button_text)
            return True
    except Exception as js_exc:
        logger.warning("[INSTAGRAM] JavaScript fallback for '{}' failed: {}", button_text, js_exc)

    logger.error("[INSTAGRAM] Could not find '{}' button", button_text)
    return False


def _dismiss_cookie_banner(driver, wait: WebDriverWait) -> None:
    """
    Instagram occasionally shows a cookie banner; accept/dismiss to unblock flow.
    Use short timeout to avoid blocking if no banner present.
    """
    from selenium.common.exceptions import TimeoutException

    # Use a short timeout for cookie banner dismissal
    short_wait = WebDriverWait(driver, 2)

    try:
        # Try multiple common cookie banner button texts
        accept_btn = short_wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//button[contains(., 'Allow essential') or contains(., 'Allow all') "
                    "or contains(., 'Accept all') or contains(., 'Allow cookies') "
                    "or contains(., 'Accept') or contains(., 'Agree')]",
                )
            )
        )
        _smart_click(driver, accept_btn)
        logger.info("[INSTAGRAM] Dismissed cookie banner")
        return
    except TimeoutException:
        pass

    # Fallback: try to click any button in cookie-related dialogs
    try:
        cookie_buttons = driver.find_elements(
            By.XPATH,
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'allow') "
            "or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept') "
            "or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree')]"
        )
        if cookie_buttons:
            _smart_click(driver, cookie_buttons[0])
            logger.info("[INSTAGRAM] Clicked cookie-related button")
            return
    except Exception:
        pass

    # Final fallback: remove overlay elements if present
    try:
        driver.execute_script(
            """
            document.querySelectorAll('[role="dialog"], [aria-label*="cookie" i], [aria-label*="Cookie" i], '
            '._a9--, [data-testid*="cookie"], [data-testid*="Cookie"]')
                    .forEach(el => el.remove());
            """
        )
        logger.info("[INSTAGRAM] Removed cookie overlays")
    except Exception:
        pass


def _dismiss_save_login(driver, wait: WebDriverWait) -> None:
    """
    Dismiss the 'Save your login info' modal by clicking 'Not now'.
    Use short timeout to avoid blocking.
    """
    from selenium.common.exceptions import TimeoutException

    # Use short timeout for save login dismissal
    short_wait = WebDriverWait(driver, 2)

    try:
        not_now = short_wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//button[normalize-space()='Not Now' or normalize-space()='Not now' "
                    "or normalize-space()='Later']",
                )
            )
        )
        _smart_click(driver, not_now)
        logger.info("[INSTAGRAM] Dismissed save login modal")
        return
    except TimeoutException:
        pass

    # Fallback: try JavaScript approach
    try:
        driver.execute_script(
            """
            document.querySelectorAll('div[role="dialog"] button, [role="button"]').forEach(btn => {
                const text = (btn.innerText || '').toLowerCase();
                if (text.includes('not now') || text.includes('later') || text.includes('skip')) {
                    btn.click();
                }
            });
            """
        )
        logger.info("[INSTAGRAM] Used JS fallback for save login dismissal")
    except Exception:
        pass
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
        driver=None
    ) -> None:
        """Upload a video to Instagram."""
        should_quit = False
        if not driver:
            driver = build_chrome_for_instagram(self.config)
            should_quit = True
            
        wait = WebDriverWait(driver, self.config.upload_timeout_seconds)

        try:
            driver.get(self.config.base_url)
            # Give page time to load initial elements
            import time
            time.sleep(2)

            _dismiss_cookie_banner(driver, wait)
            _dismiss_save_login(driver, wait)
            _debug_dump(driver, "after_modals")
            self._ensure_logged_in(driver, wait)
            self._open_create_dialog(driver, wait, post_type)
            self._upload_file(driver, wait, video_path)
            self._advance_creation_flow(driver, wait, post_type)
            self._fill_caption_and_share(driver, wait, caption)
            # Final Share click after caption
            self._click_final_share(driver, wait)
            self._wait_for_share_confirmation(driver, wait)

            logger.info("[INSTAGRAM] Uploaded {} post: {}", post_type, video_path)

            # Give user time to see the result before closing
            if not self.config.headless:
                logger.info("[INSTAGRAM] Keeping browser open for 10 seconds so you can see the result...")
                import time
                time.sleep(10)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[INSTAGRAM] Upload failed for {}", video_path)
            raise InstagramUploadError(str(exc)) from exc
        finally:
            if should_quit:
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

        # Wait for the dropdown/modal to appear
        import time
        time.sleep(3)
        _debug_dump(driver, "after_create_click")

        # After Create is clicked, a dropdown appears with Post option - click it
        if not _click_button_by_text(driver, "Post", timeout=5):
            logger.warning("[INSTAGRAM] Could not find Post option in dropdown")
        else:
            time.sleep(1)  # Wait for the upload modal to load

    def _upload_file(self, driver, wait: WebDriverWait, video_path: Path) -> None:
        """Attach video file to upload."""
        try:
            file_input = wait.until(EC.presence_of_element_located(S.FILE_INPUT))
        except Exception:
            _debug_dump(driver, "file_input")
            raise
        file_input.send_keys(str(video_path))

        # After uploading, wait a moment for processing then click Next
        import time
        time.sleep(2)  # Wait for upload to process

        if not _click_button_by_text(driver, "Next", timeout=5):
            _debug_dump(driver, "next_after_upload")

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

    def _click_final_share(self, driver, wait: WebDriverWait) -> None:
        """Click the final Share button after caption is filled."""
        import time
        time.sleep(0.5)  # Give a moment for the Share button to become available

        if not _click_button_by_text(driver, "Share", timeout=5):
            raise Exception("Could not click Share button")

    def _wait_for_share_confirmation(self, driver, wait: WebDriverWait) -> None:
        """Wait for share confirmation with bounded timeout."""
        from selenium.common.exceptions import TimeoutException

        try:
            # Use reasonable timeout for confirmation (30s for most videos)
            confirmation_wait = WebDriverWait(driver, 30)
            confirmation_wait.until(EC.presence_of_element_located(S.UPLOAD_PROGRESS_DONE))
            logger.info("[INSTAGRAM] Upload confirmation detected - post should be live!")
        except TimeoutException:
            _debug_dump(driver, "share_no_confirmation")
            logger.warning("[INSTAGRAM] Share confirmation not detected within 30s; upload likely still processing")
            # Don't raise - upload may have succeeded even if confirmation text didn't appear

