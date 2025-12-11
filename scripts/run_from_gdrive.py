#!/usr/bin/env python3
"""Run agent against videos from a Google Drive folder."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure src on path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from loguru import logger

from agent.captions import generate_captions_from_title
from agent.config import load_settings
from agent.source_gdrive import build_drive_client, build_items_from_folder
from agent.state import UploadState
from agent.workflow import run_cycle


def main() -> None:
    settings = load_settings()

    sa_json = Path(os.getenv("GDRIVE_SA_JSON", "secrets/service_account.json")).expanduser()
    folder_id = os.environ["GDRIVE_FOLDER_ID"]  # fail fast if missing

    logger.info("[WORKFLOW] Starting GDrive run: folder_id={}, sa_json={}", folder_id, sa_json)

    service = build_drive_client(sa_json)
    state = UploadState.load_default()

    items = build_items_from_folder(
        service=service,
        folder_id=folder_id,
        download_dir=Path("data/videos"),
        caption_fn=generate_captions_from_title,
        state=state,
    )

    if not items:
        print("No videos found in folder or all already processed.")
        return

    run_cycle(settings, items, platforms=["tiktok", "youtube", "instagram"])
    state.save()


if __name__ == "__main__":
    main()

