"""Instagram client for uploading videos via Selenium."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from loguru import logger
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from agent.config import InstagramConfig
from .instagram_browser import build_chrome_for_instagram
from .instagram_hitl import (
    print_operator_instructions,
    start_cdp_login_chrome,
    stop_process,
    wait_for_login,
)
from . import instagram_selectors as S


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_tag(raw: str) -> str:
    return "".join(ch if (ch.isalnum() or ch in ("-", "_")) else "_" for ch in raw)[:80]


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

    def _resolve_run_paths(self) -> tuple[str, Path]:
        run_id = self.config.run_id or os.getenv("IG_RUN_ID")
        if not run_id:
            run_id = _utc_now().strftime("%Y%m%dT%H%M%SZ")

        debug_dir = self.config.debug_dir or os.getenv("IG_DEBUG_DIR")
        debug_dir_path = Path(debug_dir) if debug_dir else Path("/tmp/ig_runs") / run_id
        debug_dir_path.mkdir(parents=True, exist_ok=True)

        # Ensure config reflects resolved paths so browser logging lands in the run folder.
        self.config.run_id = run_id
        self.config.debug_dir = debug_dir_path
        return run_id, debug_dir_path

    def _steps_path(self, debug_dir: Path) -> Path:
        return debug_dir / "steps.jsonl"

    def _write_step(
        self,
        *,
        debug_dir: Path,
        step: str,
        status: str,
        driver=None,
        extra: dict | None = None,
    ) -> None:
        payload: dict = {
            "ts": _utc_now().isoformat(),
            "step": step,
            "status": status,
        }
        if driver is not None:
            try:
                payload["url"] = driver.current_url
            except Exception:
                pass
        if extra:
            payload.update(extra)

        try:
            with self._steps_path(debug_dir).open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
        except Exception as exc:  # noqa: BLE001
            logger.warning("[INSTAGRAM] Failed to write steps.jsonl: {}", exc)

    def _dump(self, *, debug_dir: Path, driver, tag: str) -> None:
        safe = _safe_tag(tag)
        ts = _utc_now().strftime("%Y%m%dT%H%M%SZ")
        html_path = debug_dir / f"debug_{safe}_{ts}.html"
        png_path = debug_dir / f"debug_{safe}_{ts}.png"

        try:
            html_path.write_text(driver.page_source, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning("[INSTAGRAM] Failed to write HTML dump {}: {}", html_path, exc)

        try:
            driver.get_screenshot_as_file(str(png_path))
        except Exception as exc:  # noqa: BLE001
            logger.warning("[INSTAGRAM] Failed to write screenshot {}: {}", png_path, exc)

    def _classify_page(self, *, html: str, url: str) -> str:
        u = (url or "").lower()
        h = (html or "").lower()
        if "accounts/login" in u or "accounts/login" in h:
            return "LOGIN_PAGE"
        if "checkpoint" in u or "checkpoint" in h:
            return "CHECKPOINT"
        if "challenge" in u or "challenge" in h:
            return "CHALLENGE"
        if "captcha" in h or "robot" in h:
            return "CAPTCHA"
        return "UNKNOWN"

    def _write_env_json(
        self,
        *,
        debug_dir: Path,
        video_path: Path,
        post_type: str,
    ) -> None:
        payload = {
            "run_id": self.config.run_id,
            "debug_dir": str(debug_dir),
            "profile_dir": str(self.config.profile_dir),
            "headless": bool(self.config.headless),
            "base_url": str(self.config.base_url),
            "video_basename": video_path.name,
            "post_type": post_type,
            "interactive_login": bool(getattr(self.config, "interactive_login", False)),
            "interactive_timeout_secs": int(getattr(self.config, "interactive_timeout_secs", 900)),
            "cdp_port": int(getattr(self.config, "cdp_port", 9222)),
        }
        try:
            (debug_dir / "env.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning("[INSTAGRAM] Failed to write env.json: {}", exc)

    def upload(
        self,
        video_path: Path,
        caption: str,
        post_type: PostType = "feed",
        driver=None
    ) -> None:
        """Upload a video to Instagram."""
        _, debug_dir = self._resolve_run_paths()
        self._write_env_json(debug_dir=debug_dir, video_path=video_path, post_type=post_type)

        should_quit = False
        if not driver:
            self._write_step(debug_dir=debug_dir, step="driver_create", status="start")
            driver = build_chrome_for_instagram(self.config)
            should_quit = True
            self._write_step(debug_dir=debug_dir, step="driver_create", status="ok", driver=driver)
            
        wait = WebDriverWait(driver, self.config.upload_timeout_seconds)

        try:
            self._write_step(debug_dir=debug_dir, step="navigate_instagram", status="start")
            driver.get(self.config.base_url)
            # Give page time to load initial elements
            time.sleep(2)
            self._write_step(debug_dir=debug_dir, step="navigate_instagram", status="ok", driver=driver)

            self._write_step(debug_dir=debug_dir, step="dismiss_modals", status="start", driver=driver)
            _dismiss_cookie_banner(driver, wait)
            _dismiss_save_login(driver, wait)
            self._dump(debug_dir=debug_dir, driver=driver, tag="after_modals")
            self._write_step(debug_dir=debug_dir, step="dismiss_modals", status="ok", driver=driver)

            self._write_step(debug_dir=debug_dir, step="login_check", status="start", driver=driver)
            if not self._is_logged_in(driver):
                self._dump(debug_dir=debug_dir, driver=driver, tag="not_logged_in")
                html = ""
                url = ""
                title = ""
                try:
                    html = driver.page_source
                except Exception:
                    pass
                try:
                    url = driver.current_url
                except Exception:
                    pass
                try:
                    title = driver.title
                except Exception:
                    pass
                classification = self._classify_page(html=html, url=url)
                logger.warning(
                    "[INSTAGRAM] Not logged in: classification={}, title={}, url={}",
                    classification,
                    title,
                    url,
                )
                self._write_step(
                    debug_dir=debug_dir,
                    step="login_check",
                    status="not_logged_in",
                    driver=driver,
                    extra={"classification": classification, "title": title},
                )

                if getattr(self.config, "interactive_login", False) and should_quit:
                    self._write_step(debug_dir=debug_dir, step="interactive_login", status="start", driver=driver)
                    try:
                        driver.quit()
                    except Exception:
                        pass
                    print_operator_instructions(cdp_port=int(getattr(self.config, "cdp_port", 9222)))
                    proc = start_cdp_login_chrome(
                        profile_dir=Path(self.config.profile_dir),
                        debug_dir=debug_dir,
                        cdp_port=int(getattr(self.config, "cdp_port", 9222)),
                    )
                    try:
                        logged_in = wait_for_login(
                            profile_dir=Path(self.config.profile_dir),
                            timeout_secs=int(getattr(self.config, "interactive_timeout_secs", 900)),
                            poll_secs=5,
                        )
                    finally:
                        stop_process(proc)

                    if not logged_in:
                        self._write_step(
                            debug_dir=debug_dir,
                            step="interactive_login",
                            status="timeout",
                            extra={"timeout_secs": int(getattr(self.config, "interactive_timeout_secs", 900))},
                        )
                        raise InstagramNotLoggedInError("Interactive login timed out; profile still appears logged out")

                    self._write_step(debug_dir=debug_dir, step="interactive_login", status="ok")
                    driver = build_chrome_for_instagram(self.config)
                    wait = WebDriverWait(driver, self.config.upload_timeout_seconds)
                    self._write_step(debug_dir=debug_dir, step="driver_recreate", status="ok", driver=driver)
                    driver.get(self.config.base_url)
                    time.sleep(2)
                    self._dump(debug_dir=debug_dir, driver=driver, tag="post_interactive_login")

                    if not self._is_logged_in(driver):
                        self._dump(debug_dir=debug_dir, driver=driver, tag="still_not_logged_in")
                        raise InstagramNotLoggedInError("Profile still not logged in after interactive login")
                else:
                    raise InstagramNotLoggedInError("Instagram profile is not logged in")

            self._write_step(debug_dir=debug_dir, step="login_check", status="ok", driver=driver)

            self._write_step(debug_dir=debug_dir, step="open_create_dialog", status="start", driver=driver)
            self._open_create_dialog(driver, wait, post_type)
            self._write_step(debug_dir=debug_dir, step="open_create_dialog", status="ok", driver=driver)
            self._dump(debug_dir=debug_dir, driver=driver, tag="after_create_dialog")

            self._write_step(debug_dir=debug_dir, step="upload_file", status="start", driver=driver)
            self._upload_file(driver, wait, video_path)
            self._write_step(debug_dir=debug_dir, step="upload_file", status="ok", driver=driver)
            self._dump(debug_dir=debug_dir, driver=driver, tag="after_file_upload")

            self._write_step(debug_dir=debug_dir, step="advance_flow", status="start", driver=driver)
            self._advance_creation_flow(driver, wait, post_type)
            self._write_step(debug_dir=debug_dir, step="advance_flow", status="ok", driver=driver)

            self._write_step(debug_dir=debug_dir, step="fill_caption", status="start", driver=driver)
            self._fill_caption_and_share(driver, wait, caption)
            self._write_step(debug_dir=debug_dir, step="fill_caption", status="ok", driver=driver)
            self._dump(debug_dir=debug_dir, driver=driver, tag="after_caption")

            # Final Share click after caption
            self._write_step(debug_dir=debug_dir, step="click_share", status="start", driver=driver)
            self._click_final_share(driver, wait)
            self._write_step(debug_dir=debug_dir, step="click_share", status="ok", driver=driver)

            self._write_step(debug_dir=debug_dir, step="wait_confirmation", status="start", driver=driver)
            self._wait_for_share_confirmation(driver, wait)
            self._write_step(debug_dir=debug_dir, step="wait_confirmation", status="ok", driver=driver)

            logger.info("[INSTAGRAM] Uploaded {} post: {}", post_type, video_path)

            # Give user time to see the result before closing
            if not self.config.headless:
                logger.info("[INSTAGRAM] Keeping browser open for 10 seconds so you can see the result...")
                time.sleep(10)
        except Exception as exc:  # noqa: BLE001
            title = ""
            url = ""
            page_html = ""
            try:
                url = driver.current_url
            except Exception:
                pass
            try:
                title = driver.title
            except Exception:
                pass
            try:
                page_html = driver.page_source
            except Exception:
                pass
            classification = self._classify_page(html=page_html, url=url)
            logger.error(
                "[INSTAGRAM] Failure context: classification={}, title={}, url={}",
                classification,
                title,
                url,
            )
            self._write_step(
                debug_dir=debug_dir,
                step="failure",
                status="error",
                driver=driver,
                extra={"error": str(exc), "classification": classification, "title": title},
            )
            try:
                self._dump(debug_dir=debug_dir, driver=driver, tag="exception")
            except Exception:
                pass
            logger.exception("[INSTAGRAM] Upload failed for {}", video_path)
            raise InstagramUploadError(str(exc)) from exc
        finally:
            if should_quit:
                driver.quit()

    def _is_logged_in(self, driver) -> bool:
        """Best-effort check if Instagram UI shows a logged-in profile."""
        try:
            WebDriverWait(driver, 5).until(EC.presence_of_element_located(S.PROFILE_ICON))
            return True
        except Exception:
            return False

    def _open_create_dialog(self, driver, wait: WebDriverWait, post_type: PostType) -> None:
        """Open the Instagram create post dialog."""
        try:
            create_btn = wait.until(EC.element_to_be_clickable(S.CREATE_BUTTON))
        except Exception:
            raise
        _smart_click(driver, create_btn)

        # Wait for the dropdown/modal to appear
        time.sleep(3)

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
            raise
        file_input.send_keys(str(video_path))

        # After uploading, wait a moment for processing then click Next
        time.sleep(2)  # Wait for upload to process

        if not _click_button_by_text(driver, "Next", timeout=5):
            pass

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
                    raise
                try:
                    next_btn = wait.until(EC.element_to_be_clickable(S.NEXT_BUTTON))
                except Exception:
                    raise
                _smart_click(driver, next_btn)
        # Final attempt to ensure caption is visible
        wait.until(EC.presence_of_element_located(S.CAPTION_AREA))

    def _fill_caption_and_share(self, driver, wait: WebDriverWait, caption: str) -> None:
        """Fill the caption text and click share."""
        try:
            caption_el = wait.until(EC.element_to_be_clickable(S.CAPTION_AREA))
        except Exception:
            raise
        caption_el.clear()
        caption_el.send_keys(caption)

    def _click_final_share(self, driver, wait: WebDriverWait) -> None:
        """Click the final Share button after caption is filled."""
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
            logger.warning("[INSTAGRAM] Share confirmation not detected within 30s; upload likely still processing")
            # Don't raise - upload may have succeeded even if confirmation text didn't appear
