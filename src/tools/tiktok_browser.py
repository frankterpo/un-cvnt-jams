"""Chrome builder for TikTok automation (used when we need driver-level debug dumps).

We intentionally keep this small and similar to the YouTube/Instagram builders:
- headless toggle
- stable window size
- no-sandbox/dev-shm flags for Linux containers
"""

from __future__ import annotations

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from agent.config import TikTokConfig


def build_chrome_for_tiktok(config: TikTokConfig) -> webdriver.Chrome:
    options = Options()
    if config.headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,800")
    return webdriver.Chrome(options=options)


