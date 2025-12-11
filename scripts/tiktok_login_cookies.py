#!/usr/bin/env python3
"""
Headful helper to capture TikTok cookies and save them to a Netscape-format file.

Usage:
    PYTHONPATH=src python scripts/tiktok_login_cookies.py \
        --cookies-path /abs/path/to/tiktok_cookies.txt

Notes:
- Runs headful by default (you need to log in manually).
- After you see TikTok load, log in, then return to the terminal and press Enter.
- Cookies are saved in Netscape format, which `tiktok-uploader` accepts via `cookies=` path.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

from loguru import logger

# Add src/ to path if executed directly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent.config import TikTokConfig
from tools.tiktok_browser import build_chrome_for_tiktok


def _netscape_dump(cookies: Iterable[dict], dest: Path) -> None:
    """
    Write cookies in Netscape cookie file format.
    Format:
    domain<TAB>flag<TAB>path<TAB>secure<TAB>expiry<TAB>name<TAB>value
    """
    lines = ["# Netscape HTTP Cookie File"]
    for c in cookies:
        domain = c.get("domain", "")
        flag = "TRUE" if domain.startswith(".") else "FALSE"
        path = c.get("path", "/")
        secure = "TRUE" if c.get("secure", False) else "FALSE"
        expiry = str(int(c.get("expiry", 0))) if c.get("expiry") is not None else "0"
        name = c.get("name", "")
        value = c.get("value", "")
        lines.append("\t".join([domain, flag, path, secure, expiry, name, value]))

    dest.write_text("\n".join(lines))
    logger.info("[TIKTOK] Saved cookies to {}", dest)


def main() -> None:
    parser = argparse.ArgumentParser(description="Login to TikTok and save cookies.")
    parser.add_argument(
        "--cookies-path",
        type=Path,
        required=True,
        help="Destination path for TikTok cookies (Netscape format)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run headless (not recommended for interactive login)",
    )
    args = parser.parse_args()

    dest = args.cookies_path.expanduser().resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)

    cfg = TikTokConfig(
        cookies_path=dest,  # placeholder; we only need headless flag here
        headless=args.headless,
    )

    if cfg.headless:
        logger.warning("[TIKTOK] Headless login is unlikely to work. Prefer headful.")

    driver = build_chrome_for_tiktok(cfg)
    try:
        driver.get("https://www.tiktok.com/login")
        input("Complete login in the browser, then press Enter here to save cookies...")
        cookies = driver.get_cookies()
        _netscape_dump(cookies, dest)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()


