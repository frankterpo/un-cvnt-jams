"""Human-in-the-loop (HITL) helpers for Instagram login on EC2.

This module intentionally avoids printing secrets (cookies/session values). It
only uses best-effort heuristics to detect whether a profile likely has an
Instagram authenticated session.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import time
from pathlib import Path

from loguru import logger


def _find_cookie_db(profile_dir: Path) -> Path | None:
    """
    Find a Chrome Cookies sqlite DB under a Chrome --user-data-dir.

    We avoid recursion loops; only scan a small number of likely locations.
    """
    candidates = [
        profile_dir / "Default" / "Cookies",
        profile_dir / "Profile 1" / "Cookies",
        profile_dir / "Profile 2" / "Cookies",
    ]
    for p in candidates:
        if p.exists():
            return p

    for child in profile_dir.iterdir():
        if not child.is_dir():
            continue
        p = child / "Cookies"
        if p.exists():
            return p
    return None


def _has_instagram_session_cookie(profile_dir: Path) -> bool:
    """
    Best-effort check: does the Cookies DB contain Instagram session cookies?

    This does NOT read or print cookie values.
    """
    cookie_db = _find_cookie_db(profile_dir)
    if not cookie_db:
        return False

    try:
        uri = f"file:{cookie_db.as_posix()}?mode=ro&immutable=1"
        conn = sqlite3.connect(uri, uri=True, timeout=1)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COUNT(*) FROM cookies
                WHERE host_key LIKE '%instagram.com%'
                  AND name IN ('sessionid', 'ds_user_id')
                """
            )
            row = cur.fetchone()
            return bool(row and int(row[0]) > 0)
        finally:
            conn.close()
    except Exception:
        return False


def print_operator_instructions(*, cdp_port: int) -> None:
    logger.info("[INSTAGRAM] Interactive login required.")
    logger.info("[INSTAGRAM] On your laptop, start port-forwarding with SSM:")
    params = f'{{"portNumber":["{cdp_port}"],"localPortNumber":["{cdp_port}"]}}'
    logger.info(
        "aws ssm start-session --region us-east-1 --target <INSTANCE_ID> "
        "--document-name AWS-StartPortForwardingSession "
        "--parameters '{}'",
        params,
    )
    logger.info("[INSTAGRAM] Then open: http://127.0.0.1:{}", cdp_port)
    logger.info("[INSTAGRAM] Click 'inspect' on the Instagram tab, then enable 'Show Screencast'.")
    logger.info("[INSTAGRAM] Complete login / checkpoint / 2FA as needed, then leave the screencast open.")


def start_cdp_login_chrome(*, profile_dir: Path, debug_dir: Path, cdp_port: int) -> subprocess.Popen:
    debug_dir.mkdir(parents=True, exist_ok=True)
    out_path = debug_dir / "cdp_chrome.out"
    err_path = debug_dir / "cdp_chrome.err"

    out_f = out_path.open("ab")
    err_f = err_path.open("ab")

    cmd = [
        "google-chrome",
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--remote-debugging-address=127.0.0.1",
        f"--remote-debugging-port={cdp_port}",
        f"--user-data-dir={profile_dir}",
        "https://www.instagram.com/",
    ]

    logger.info("[INSTAGRAM] Starting CDP Chrome for interactive login (port={})", cdp_port)
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=out_f,
            stderr=err_f,
            close_fds=True,
            env={**os.environ},
        )
        return proc
    finally:
        try:
            out_f.close()
        except Exception:
            pass
        try:
            err_f.close()
        except Exception:
            pass


def stop_process(proc: subprocess.Popen, timeout_secs: int = 10) -> None:
    try:
        proc.terminate()
    except Exception:
        return
    try:
        proc.wait(timeout=timeout_secs)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def wait_for_login(*, profile_dir: Path, timeout_secs: int, poll_secs: int = 5) -> bool:
    deadline = time.monotonic() + timeout_secs
    while time.monotonic() < deadline:
        if _has_instagram_session_cookie(profile_dir):
            return True
        time.sleep(poll_secs)
    return False
