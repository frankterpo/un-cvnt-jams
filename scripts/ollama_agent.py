#!/usr/bin/env python3
"""Ollama-powered planner that routes posts to platform clients."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import requests

# Ensure src on path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from loguru import logger

from agent.captions import generate_captions_from_title
from agent.config import load_settings
from agent.source_gdrive import build_drive_client, build_items_from_folder
from agent.state import UploadState
from agent.workflow import VideoItem, run_cycle


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")


SYSTEM_PROMPT = """
You are a posting scheduler agent.

You have these conceptual tools (Python already implements them):
- list_pending_videos(): returns a list of objects: { "id": string, "title": string, "filename": string }.
- post_to_tiktok(video_id): post that video to TikTok.
- post_to_youtube(video_id): post that video to YouTube.
- post_to_instagram(video_id): post that video to Instagram.

Your job:
- Decide which videos should go to which platforms.
- Use filename/title heuristics to guess content type:
  - Titles or filenames containing words like "short", "clip", "reel", "vertical" → more likely TikTok and Instagram.
  - Titles or filenames containing "podcast", "talk", "long", "episode" → more likely YouTube.
  - If unsure, you MAY post to multiple platforms.

Posting constraints:
- Post AT MOST 3 videos per platform in a single run.
- Prefer diversity: if there are many videos, try to spread them across platforms instead of sending everything everywhere.
- You MAY also choose to NOT post a given video at all in this run.

Output format (very strict):
- You MUST output ONLY a single JSON object with this exact shape:

{
  "actions": [
    { "tool": "post_to_tiktok", "args": { "video_id": "..." } },
    { "tool": "post_to_youtube", "args": { "video_id": "..." } },
    { "tool": "post_to_instagram", "args": { "video_id": "..." } }
  ]
}

Rules:
- "actions" MUST be a list.
- Each "tool" MUST be one of: "post_to_tiktok", "post_to_youtube", "post_to_instagram".
- Each "args" MUST contain exactly one key: "video_id", set to a string.
- You MUST only reference video_ids from the provided list.
- No extra keys, no comments, no markdown, no explanations.
"""


def call_ollama(videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ask Ollama which tool calls to execute; expect strict JSON with `actions`."""
    user_prompt = (
        "Pending videos:\n"
        f"{json.dumps(videos, ensure_ascii=False)}\n\n"
        "Return ONLY the JSON object with the `actions` array as specified."
    )

    logger.info("[PLANNER] Calling Ollama model={} url={}", OLLAMA_MODEL, OLLAMA_URL)
    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.strip()},
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=120,
    )
    resp.raise_for_status()
    body = resp.json()

    content = body.get("message", {}).get("content", "")
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise RuntimeError(f"Ollama returned non-JSON content: {content!r}")
        data = json.loads(content[start : end + 1])

    actions = data.get("actions") or []
    if not isinstance(actions, list):
        raise RuntimeError(f"Ollama JSON missing 'actions' list: {data}")
    return actions


def list_pending_from_gdrive() -> list[VideoItem]:
    """Use GDrive to produce VideoItem objects; captions via stub generator."""
    sa_json = Path(os.getenv("GDRIVE_SA_JSON", "secrets/service_account.json")).expanduser()
    folder_id = os.environ["GDRIVE_FOLDER_ID"]

    service = build_drive_client(sa_json)
    state = UploadState.load_default()

    items = build_items_from_folder(
        service=service,
        folder_id=folder_id,
        download_dir=Path("data/videos"),
        caption_fn=generate_captions_from_title,
        state=state,
    )
    return items


def main() -> None:
    settings = load_settings()

    items = list_pending_from_gdrive()
    if not items:
        logger.info("[PLANNER] No pending items.")
        return

    videos_meta = [
        {
            "id": it.id,
            "title": it.path.stem,
            "filename": it.path.name,
        }
        for it in items
    ]
    actions = call_ollama(videos_meta)
    logger.info("[PLANNER] Ollama returned {} action(s)", len(actions))

    by_id: dict[str, VideoItem] = {it.id: it for it in items}

    for action in actions:
        tool = action.get("tool")
        args = action.get("args") or {}
        video_id = args.get("video_id")
        if not video_id:
            continue

        item = by_id.get(video_id)
        if not item:
            continue

        if tool == "post_to_tiktok":
            logger.info("[PLANNER] Executing post_to_tiktok video_id={}", video_id)
            run_cycle(settings, [item], platforms=["tiktok"])
        elif tool == "post_to_youtube":
            logger.info("[PLANNER] Executing post_to_youtube video_id={}", video_id)
            run_cycle(settings, [item], platforms=["youtube"])
        elif tool == "post_to_instagram":
            logger.info("[PLANNER] Executing post_to_instagram video_id={}", video_id)
            run_cycle(settings, [item], platforms=["instagram"])
        else:
            continue


if __name__ == "__main__":
    main()

