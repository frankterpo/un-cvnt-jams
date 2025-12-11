# TikTok Agent Integration Plan (using `wkaisertexas/tiktok-uploader`)

Target environment: Python 3.11+, Cursor (Opus 4.5)  
Purpose: Build a robust `TikTokClient` around the `tiktok-uploader` library and expose simple programmatic hooks for the main social agent (GDrive → caption → TikTok upload).

Reference GitHub repo: `wkaisertexas/tiktok-uploader`  
Reference PyPI package: `tiktok-uploader`

---

## 0. Project assumptions

- Monorepo root: `social-agent/`
- Shared modules already exist or will exist:
  - `src/tools/gdrive_client.py` – Google Drive download
  - `src/agent/workflow.py` – orchestrator
  - `src/agent/config.py` – Pydantic config models
- TikTok should **not** use any official TikTok API; only browser automation via `tiktok-uploader`’s Selenium-based backend.

---

## 1. Dependencies & setup

**Task:** Update project dependencies to include `tiktok-uploader`.

1. In `pyproject.toml` (or `requirements.txt` if used):

   ```toml
   [project]
   name = "social-agent"
   requires-python = ">=3.11"

   [project.dependencies]
   tiktok-uploader = "*"
   pydantic = ">=2.0"
   loguru = "*"
   ```

2. Ensure Selenium + browser dependencies are satisfied automatically by `tiktok-uploader`. If not, add:

   ```txt
   selenium
   webdriver-manager
   ```

3. Add a config section for TikTok to `src/agent/config.py`:

   ```python
   from pydantic import BaseModel
   from pathlib import Path

   class TikTokConfig(BaseModel):
       cookies_path: Path          # path to cookies.txt
       use_proxy: bool = False
       proxy_host: str | None = None
       proxy_port: int | None = None
       proxy_username: str | None = None
       proxy_password: str | None = None
       headless: bool = True
   ```

4. Extend global `Settings` model to include `tiktok: TikTokConfig`.

---

## 2. TikTok cookies & auth workflow

**Goal:** Rely on exported browser cookies (NetScape `cookies.txt`) to authenticate uploads.

1. Define a convention: TikTok cookies stored at `secrets/tiktok_cookies.txt` in local dev, and provided via environment/GitHub Secrets in CI.

2. Implement `src/tools/tiktok_auth.py`:

   ```python
   from __future__ import annotations
   from pathlib import Path
   from tiktok_uploader.auth import AuthBackend
   from agent.config import TikTokConfig

   def build_auth(config: TikTokConfig) -> AuthBackend:
       cookies_path = config.cookies_path.expanduser().resolve()
       if not cookies_path.is_file():
           raise FileNotFoundError(f"TikTok cookies file not found: {cookies_path}")
       return AuthBackend(cookies=str(cookies_path))
   ```

3. For proxies: add a helper that returns a `dict` compatible with `tiktok-uploader`’s proxy handling (host, port, optional user/pass).

---

## 3. `TikTokClient` design

**Goal:** Provide a minimal, strongly-typed client that the agent can call.

Create file: `src/tools/tiktok_client.py`:

```python
from __future__ import annotations
from pathlib import Path
from typing import Iterable

from tiktok_uploader.upload import upload_video, upload_videos
from tiktok_uploader.auth import AuthBackend
from agent.config import TikTokConfig
from .tiktok_auth import build_auth

class TikTokClient:
    """
    Thin wrapper around `tiktok-uploader` providing a stable programmatic interface
    for the social agent.
    """

    def __init__(self, config: TikTokConfig):
        self.config = config
        self.auth: AuthBackend = build_auth(config)

    def upload_single(
        self,
        video_path: Path,
        description: str,
        *,
        allow_comments: bool = True,
        allow_duet: bool = True,
        allow_stitch: bool = True,
        schedule_time: str | None = None,   # ISO or TikTok-expected format
    ) -> None:
        # TODO: wire through any tiktok-uploader options for proxy, headless, etc.
        upload_video(
            str(video_path),
            description=description,
            auth=self.auth,
            # additional kwargs: proxy, schedule, etc.
        )

    def upload_batch(
        self,
        items: Iterable[tuple[Path, str]],
    ) -> None:
        paths = [str(p) for p, _ in items]
        descs = [d for _, d in items]
        upload_videos(
            paths,
            descriptions=descs,
            auth=self.auth,
        )
```

Implementation details for extra keyword args (like proxies, scheduling) should mirror the official `tiktok-uploader` README and code.

---

## 4. Integration with the agent workflow

**Goal:** Add a TikTok upload step into the GDrive → caption → publish pipeline.

In `src/agent/workflow.py`:

1. Add a function-level import:

   ```python
   from tools.tiktok_client import TikTokClient
   from agent.config import Settings
   ```

2. Implement a helper:

   ```python
   def publish_to_tiktok(
       settings: Settings,
       video_path: Path,
       caption: str,
   ) -> None:
       client = TikTokClient(settings.tiktok)
       client.upload_single(video_path, caption)
   ```

3. Inside the main `run_cycle()` or equivalent:

   - After downloading a video from Drive and generating a caption via LLM:

     ```python
     if "tiktok" in target_platforms:
         publish_to_tiktok(settings, video_path, captions["tiktok"])
     ```

---

## 5. Error handling, logging, and idempotency

**Goal:** Make failures observable and retriable.

1. Introduce a basic `UploadResult` dataclass in `tiktok_client.py` if desired, but minimally:

   - Log success/failure using a central logger:
     ```python
     from loguru import logger
     ```
   - Catch exceptions around `upload_video` and rethrow custom `TikTokUploadError`.

2. Add a simple persistent store (e.g. SQLite or JSON file) to prevent re-uploading the same Drive file to TikTok multiple times:

   - Table/structure: `(drive_file_id, platform, status, last_updated)`.

   - Before calling `publish_to_tiktok`, check if there is already a successful TikTok record.

---

## 6. Local development workflow

1. Dev machine steps:
   - Log into TikTok in normal Chrome.
   - Use a “cookies.txt” extension to export cookies to `secrets/tiktok_cookies.txt`.
   - Run a local script:

     ```bash
     python -m scripts.test_tiktok_upload        --video path/to/video.mp4        --caption "Test upload from social-agent"
     ```

2. Confirm upload appears in the test TikTok account.

---

## 7. GitHub Actions / self-hosted runner considerations

Even though `tiktok-uploader` spins up its own Selenium machinery, the runner must:

- Have Chrome/Chromium installed.
- Allow outbound connections to TikTok.
- Be stable IP-wise to avoid constant security challenges.

Expose cookies via `TIKTOK_COOKIES` secret, write them to a file before `run_agent` is executed.

---

## 8. Extension points

Later enhancements for Opus to implement:

- Per-account TikTok configs (multiple cookies files).
- Scheduling future posts via the library’s schedule feature.
- Dynamic captions from LLM with per-video hashtags and mentions.
- Proxy-aware uploads (different IPs per account).
