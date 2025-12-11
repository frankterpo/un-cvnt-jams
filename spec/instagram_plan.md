# Instagram Agent Integration Plan (Custom Selenium, `autopost_instagram` as Reference)

Target environment: Python 3.11+, Cursor (Opus 4.5)  
Purpose: Implement a robust `InstagramClient` using Selenium + Chrome profiles to upload feed posts / Reels via the web UI, **without** relying on Instagram APIs.  
Reference GitHub repo (for ideas only): `leothewolf/autopost_instagram` – small Selenium example for video posting.

---

## 0. Constraints & goals

- No official Instagram API usage; everything is done via **browser automation**.
- We maintain our own `InstagramClient` because there is no mature, high-star Selenium uploader.
- `autopost_instagram` is used purely as:
  - an example of selecting file inputs and posting via the Instagram UI;
  - not as a library dependency.

---

## 1. Config & dependencies

Add Selenium and Chrome driver dependencies (if not already present):

```txt
selenium
webdriver-manager
```

Extend `Settings` with:

```python
from pydantic import BaseModel
from pathlib import Path

class InstagramConfig(BaseModel):
    profile_dir: Path            # Chrome user data dir for logged-in IG account
    base_url: str = "https://www.instagram.com"
    headless: bool = True
    upload_timeout_seconds: int = 120
```

---

## 2. Browser setup

Create `src/tools/instagram_browser.py`:

```python
from __future__ import annotations
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def build_chrome_for_instagram(profile_dir: Path, headless: bool = False) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)
    return driver
```

**Requirement:** `profile_dir` must point to a Chrome profile where a human has already logged into Instagram and completed any 2FA checkpoints.

---

## 3. Selector abstraction

Create `src/tools/instagram_selectors.py` to isolate DOM details:

```python
from selenium.webdriver.common.by import By

# Example selectors (to be validated/updated against live DOM):
CREATE_BUTTON = (By.CSS_SELECTOR, "svg[aria-label='New post'], svg[aria-label='Create']")
FILE_INPUT = (By.CSS_SELECTOR, "input[type='file']")
NEXT_BUTTON = (By.XPATH, "//div[text()='Next']/.. | //button[text()='Next']")
CAPTION_AREA = (By.XPATH, "//textarea[@aria-label='Write a caption…'] | //div[@aria-label='Write a caption…']")
SHARE_BUTTON = (By.XPATH, "//div[text()='Share']/.. | //button[text()='Share']")
UPLOAD_PROGRESS_DONE = (By.XPATH, "//*[contains(text(),'Your post has been shared') or contains(text(),'Post shared')]")
```

Opus should refine these selectors by inspecting current Instagram web UI; `autopost_instagram` can be used as a reference for older patterns.

---

## 4. `InstagramClient` design

Create `src/tools/instagram_client.py`:

```python
from __future__ import annotations
from pathlib import Path
from typing import Literal

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from agent.config import InstagramConfig
from .instagram_browser import build_chrome_for_instagram
from . import instagram_selectors as S

PostType = Literal["feed", "reel"]  # For now, UI flow is very similar

class InstagramClient:
    def __init__(self, config: InstagramConfig):
        self.config = config

    def upload(
        self,
        video_path: Path,
        caption: str,
        post_type: PostType = "feed",
    ) -> None:
        driver = build_chrome_for_instagram(self.config.profile_dir, self.config.headless)
        wait = WebDriverWait(driver, self.config.upload_timeout_seconds)

        try:
            driver.get(self.config.base_url)

            # 1. Ensure logged in (basic heuristic)
            # If not logged in, user must fix profile manually.
            self._assert_logged_in(wait)

            # 2. Open "Create" dialog
            create_btn = wait.until(EC.element_to_be_clickable(S.CREATE_BUTTON))
            create_btn.click()

            # 3. Attach video file
            file_input = wait.until(EC.presence_of_element_located(S.FILE_INPUT))
            file_input.send_keys(str(video_path))

            # 4. Wait for preview and click "Next" until caption step
            self._click_next_until_caption(driver, wait)

            # 5. Fill caption
            caption_el = wait.until(EC.element_to_be_clickable(S.CAPTION_AREA))
            caption_el.clear()
            caption_el.send_keys(caption)

            # 6. Click "Share"
            share_btn = wait.until(EC.element_to_be_clickable(S.SHARE_BUTTON))
            share_btn.click()

            # 7. Wait for confirmation
            wait.until(EC.presence_of_element_located(S.UPLOAD_PROGRESS_DONE))
        finally:
            driver.quit()

    def _assert_logged_in(self, wait: WebDriverWait) -> None:
        # Simple heuristic: check for presence of the profile icon or "Create" button
        # If not found within timeout, raise a custom NotLoggedInError.
        ...

    def _click_next_until_caption(self, driver, wait: WebDriverWait) -> None:
        # Some flows have one or two "Next" screens (crop/aspect/filter)
        # Click NEXT_BUTTON up to N times until caption area is visible or timeout.
        ...
```

Opus should implement `_assert_logged_in` and `_click_next_until_caption` using robust conditions based on the current DOM.

---

## 5. Integration into agent workflow

In `src/agent/workflow.py`:

```python
from tools.instagram_client import InstagramClient

def publish_to_instagram(settings: Settings, video_path: Path, caption: str) -> None:
    client = InstagramClient(settings.instagram)
    client.upload(video_path, caption, post_type="feed")  # or "reel" once flow is verified
```

In `run_cycle()`:

- If `"instagram"` is in the list of target platforms for a given video, call `publish_to_instagram`.

Caption input for Instagram should come from the LLM, but the agent can reuse the same caption as TikTok and modify it slightly (different hashtag strategy, no clickbait that violates IG guidelines, etc.).

---

## 6. Manual login / profile bootstrapping

Create a helper script: `src/ui_debug/instagram_login.py`:

```python
from pathlib import Path
from tools.instagram_browser import build_chrome_for_instagram

def main():
    profile_dir = Path("profiles/instagram-main")
    driver = build_chrome_for_instagram(profile_dir, headless=False)
    driver.get("https://www.instagram.com/accounts/login/")
    # Human logs in & completes any 2FA
    input("Press Enter once logged in and Instagram home is visible...")
    driver.quit()

if __name__ == "__main__":
    main()
```

Usage:

1. Run this script locally to create a persistent profile with a logged-in session.
2. Set `instagram.profile_dir` to that path in config.

---

## 7. Testing and resilience

1. Add a manual test script `scripts/test_instagram_upload.py`:

   ```python
   from pathlib import Path
   from agent.config import load_settings
   from tools.instagram_client import InstagramClient

   def main():
       settings = load_settings()
       client = InstagramClient(settings.instagram)
       client.upload(Path("sample_videos/ig_test.mp4"), "Testing Instagram upload via Selenium")

   if __name__ == "__main__":
       main()
   ```

2. Run it against a **throwaway Instagram account** before using on any real profile.

3. When Instagram UI changes:
   - Update selectors in `instagram_selectors.py` only.
   - Keep `InstagramClient` logic stable.

---

## 8. Future improvements

- Differentiate flows for **Reels vs feed posts** if the web UI diverges:
  - Reels may use a different entrypoint or additional options.
- Add support for:
  - Location tagging.
  - Mentioning other accounts in the caption (just text).
- Integrate random delays and small human-like pauses between actions to reduce automation fingerprints.
