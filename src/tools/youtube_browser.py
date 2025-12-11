"""Browser setup for YouTube uploads."""

from __future__ import annotations

from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def build_chrome_for_youtube(profile_dir: Path, headless: bool = False) -> webdriver.Chrome:
    """Build Chrome driver for YouTube uploads."""
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)
    return driver

