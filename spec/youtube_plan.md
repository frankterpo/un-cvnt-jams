# YouTube Agent Integration Plan (using `linouk23/youtube_uploader_selenium` as base)

Target environment: Python 3.11+, Cursor (Opus 4.5)  
Purpose: Build a modern `YouTubeClient` that uploads videos via Selenium to YouTube Studio, **borrowing and updating** logic from `linouk23/youtube_uploader_selenium`.

Reference GitHub repo (reference only, not direct dependency): `linouk23/youtube_uploader_selenium`

---

## 0. Rationale

- `youtube_uploader_selenium` provides a complete, battle-tested upload flow but targets **older Firefox/Selenium** and uses `selenium_firefox` abstractions.
- Plan: **vendor** (copy) the relevant upload logic into our repo, upgrade it to Selenium 4 and Chrome or modern Firefox, and wrap it in a clean `YouTubeClient` API.

---

## 1. Code import strategy

Create a new module: `src/tools/youtube_legacy/`:

- Files to recreate (inspired by the repo):
  - `constants.py` – selectors/XPaths, URL constants.
  - `uploader.py` – core upload flow, but rewritten.
- Keep the original structure recognizable so future updates from upstream are easier.

Implementation tasks for Opus:

1. Read upstream `upload.py` and `Constant.py` and reconstruct equivalent classes:
   - Replace any `selenium_firefox` imports with standard `selenium.webdriver` imports.
   - Switch from Firefox-only to Chrome (or keep both behind a config flag).

2. Define a `YouTubeMetadata` model:

   ```python
   from pydantic import BaseModel
   from datetime import datetime

   class YouTubeMetadata(BaseModel):
       title: str
       description: str
       tags: list[str] = []
       publish_at: datetime | None = None  # None → publish immediately
   ```

3. For compatibility, support reading metadata from JSON if needed, but prefer programmatic calls from the agent.

---

## 2. Browser setup for YouTube

Create `src/tools/youtube_browser.py`:

```python
from __future__ import annotations
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from pathlib import Path

def build_chrome_for_youtube(profile_dir: Path, headless: bool = False) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)
    return driver
```

- `profile_dir` should point to a Chrome profile already logged in to the YouTube channel (manual login once).

Extend `Settings` with:

```python
class YouTubeConfig(BaseModel):
    profile_dir: Path
    upload_url: str = "https://studio.youtube.com"
    headless: bool = True
```

---

## 3. `YouTubeClient` design

Create `src/tools/youtube_client.py`:

```python
from __future__ import annotations
from pathlib import Path
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from agent.config import YouTubeConfig
from .youtube_browser import build_chrome_for_youtube
from .metadata import YouTubeMetadata  # defined as above

class YouTubeClient:
    def __init__(self, config: YouTubeConfig):
        self.config = config

    def upload_video(self, video_path: Path, meta: YouTubeMetadata) -> str:
        """
        Uploads a video and returns the YouTube video ID.
        """
        driver = build_chrome_for_youtube(self.config.profile_dir, self.config.headless)
        wait = WebDriverWait(driver, 60)

        try:
            driver.get("https://studio.youtube.com")
            # TODO: handle potential redirect to login if profile isn't logged in.

            # 1. Click "Create" -> "Upload videos"
            # 2. Interact with file input:
            #    input[type=\"file\"] for video upload
            # 3. Fill title/description
            # 4. Set "No, it's not made for kids" etc.
            # 5. Optional scheduling if meta.publish_at is set
            # 6. Wait until final confirmation and parse video ID from URL

            # Use upstream repo as a reference for the DOM steps and XPaths.

            video_id = self._extract_video_id(driver.current_url)
            return video_id
        finally:
            driver.quit()

    def _extract_video_id(self, url: str) -> str:
        # Implement parsing from Studio URL or watch URL
        ...
```

Opus should:

- Inspect current YouTube Studio DOM (manually by developer) and define robust selectors in a local `selectors.py` module instead of hard-coded strings inside methods.
- Mirror logical flow from `youtube_uploader_selenium/upload.py`:
  - Wait for upload completion.
  - Navigate through the stepper (Details → Checks → Visibility).
  - If `publish_at` is set, choose “Schedule” and pick the date/time.

---

## 4. Integration with the main agent

In `src/agent/workflow.py`:

```python
from tools.youtube_client import YouTubeClient
from tools.youtube_metadata import YouTubeMetadata

def publish_to_youtube(settings: Settings, video_path: Path, caption_data: dict) -> str:
    """
    caption_data is the LLM-generated structure for YouTube:
    {
        "title": "...",
        "description": "...",
        "tags": ["..."],
        "publish_at": "2025-12-08T09:00:00Z" or None
    }
    """
    meta = YouTubeMetadata(
        title=caption_data["title"],
        description=caption_data["description"],
        tags=caption_data.get("tags", []),
        publish_at=parse_iso_dt(caption_data.get("publish_at")) if caption_data.get("publish_at") else None,
    )

    client = YouTubeClient(settings.youtube)
    video_id = client.upload_video(video_path, meta)
    return video_id
```

`run_cycle()` should call `publish_to_youtube` for videos where `"youtube"` is included in the target platforms.

---

## 5. Handling YouTube’s “browser not secure” / challenge flows

- If YouTube flags the Selenium-driven browser as “not secure”, mitigate by:
  - Using a **real Chrome binary** and profile that is used interactively on the same machine.
  - Avoid spoofing UA; keep defaults.
- For 2FA/accounts with high security, keep the login step manual:
  - The first run should be interactive (headless=False).
  - Once logged in, re-run the workflow with `headless=True` using the same profile directory.

---

## 6. Testing & maintenance

1. Add `tests/manual/test_youtube_upload.py` which:
   - Takes a small test video and a test metadata JSON.
   - Calls `YouTubeClient.upload_video`.
   - Prints or asserts that a non-empty video ID is returned.

2. Any time Selenium, Chrome, or YouTube UI changes:
   - Update `selectors.py` only.
   - Keep `YouTubeClient` logic stable.

3. Maintain a small `CHANGELOG_YOUTUBE.md` summarizing selector changes and breaking behavior to keep synchronization with upstream ideas from `youtube_uploader_selenium`.

---

## 7. Future improvements

- Add playlist assignment and visibility options (Public/Unlisted).
- Enable thumbnail upload by extending flow to include thumbnail file input.
- Add LLM-driven title/description optimization, but keep that outside `YouTubeClient` to preserve clean separation of concerns.
