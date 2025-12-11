"""Browser setup for Instagram uploads."""

from __future__ import annotations

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from agent.config import InstagramConfig


def build_chrome_for_instagram(config: InstagramConfig) -> webdriver.Chrome:
    """Build Chrome driver for Instagram uploads."""
    options = Options()
    if config.headless:
        options.add_argument("--headless=new")
    options.add_argument(f"--user-data-dir={config.profile_dir}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,800")
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)
    return driver

