"""Browser setup for Instagram uploads."""

from __future__ import annotations

from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from agent.config import InstagramConfig


def build_chrome_for_instagram(config: InstagramConfig) -> webdriver.Chrome:
    """Build Chrome driver for Instagram uploads."""
    debug_dir = Path(config.debug_dir) if config.debug_dir else None
    if debug_dir:
        debug_dir.mkdir(parents=True, exist_ok=True)

    options = Options()
    if config.headless:
        options.add_argument("--headless=new")
    options.add_argument(f"--user-data-dir={config.profile_dir}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,800")
    options.add_argument("--start-maximized")

    if debug_dir:
        chrome_log_path = debug_dir / "chrome.log"
        options.add_argument("--enable-logging")
        options.add_argument("--v=1")
        options.add_argument(f"--log-file={chrome_log_path}")

    if debug_dir:
        service = Service(log_output=str(debug_dir / "chromedriver.log"))
        driver = webdriver.Chrome(options=options, service=service)
    else:
        driver = webdriver.Chrome(options=options)
    return driver
