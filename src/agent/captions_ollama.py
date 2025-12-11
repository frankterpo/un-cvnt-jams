"""Platform-specific captions via Ollama (strict JSON)."""

from __future__ import annotations

import json
import os
from typing import Any, Dict

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL_CAPTIONS", os.getenv("OLLAMA_MODEL", "llama3.1"))


CAPTION_SYSTEM_PROMPT = """
You generate platform-specific captions for short video content.

Input:
- A short title and optional context string.

Output:
- STRICT JSON only, with this shape:

{
  "tiktok": "short caption string",
  "instagram": "short caption string",
  "youtube": {
    "title": "YouTube title string",
    "description": "YouTube description string",
    "tags": ["tag1", "tag2"]
  }
}

Rules:
- Return ONLY the JSON object, no markdown, no comments, no explanations.
- Captions should be natural, concise, and avoid clickbait.
- Use hashtags sparingly (0–3) and only at the end of TikTok/Instagram captions.
- Do NOT mention the word "shorts" explicitly unless clearly needed.
"""


def generate_captions_with_ollama(title: str, context: str | None = None) -> Dict[str, Any]:
    """Ask Ollama to generate platform-specific captions."""
    user_content = {
        "title": title,
        "context": context or "",
    }
    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": CAPTION_SYSTEM_PROMPT.strip()},
                {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
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
            raise RuntimeError(f"Ollama returned non-JSON caption content: {content!r}")
        data = json.loads(content[start : end + 1])

    if "tiktok" not in data or "instagram" not in data or "youtube" not in data:
        raise RuntimeError(f"Caption JSON missing expected keys: {data}")

    yt = data["youtube"]
    yt.setdefault("tags", [])
    return data

