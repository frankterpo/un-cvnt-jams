"""Optional AI-powered selector suggester using Ollama.

This module provides a fallback mechanism for suggesting selectors
when standard selectors fail. It is NOT wired into the main flow
by default - use behind a feature flag if selectors break often.

Example usage (behind flag):
    if USE_AI_LOCATOR:
        selector = ai_locator.suggest_selector("tiktok_upload_button", html)
"""

from __future__ import annotations

import json
import os
from typing import Literal

import requests
from loguru import logger

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")

# Feature flag - set to True to enable AI locator
USE_AI_LOCATOR = os.getenv("USE_AI_LOCATOR", "false").lower() == "true"

SelectorRole = Literal[
    "tiktok_upload_button",
    "tiktok_caption_input",
    "tiktok_post_button",
    "instagram_share_button",
    "instagram_create_button",
    "instagram_caption_area",
]


SYSTEM_PROMPT = """
You are a CSS/XPath selector generator for web automation.

Given:
- A role describing what element to find (e.g., "tiktok_upload_button")
- HTML snippet from the page

Output:
- STRICT JSON only with this shape:

{
  "selector_type": "css" | "xpath",
  "selector": "the actual selector string",
  "confidence": 0.0-1.0
}

Rules:
- Return ONLY the JSON object, no markdown, no comments, no explanations.
- Prefer CSS selectors when possible (faster, more stable).
- Use XPath only if CSS cannot uniquely identify the element.
- Selectors should be robust (use attributes like aria-label, data-testid, id when available).
- Avoid overly specific selectors that break on minor UI changes.
"""


def suggest_selector(role: SelectorRole, html: str) -> dict[str, str | float] | None:
    """
    Ask Ollama to suggest a selector for a given role and HTML snippet.
    
    Returns None if AI locator is disabled or if the request fails.
    """
    if not USE_AI_LOCATOR:
        return None

    user_content = {
        "role": role,
        "html_snippet": html[:5000],  # Limit HTML size
    }

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "stream": False,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT.strip()},
                    {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
                ],
            },
            timeout=30,
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
                logger.warning("Ollama returned non-JSON selector suggestion: {}", content[:200])
                return None
            data = json.loads(content[start : end + 1])

        if "selector_type" not in data or "selector" not in data:
            logger.warning("Ollama selector JSON missing required keys: {}", data)
            return None

        return {
            "selector_type": data["selector_type"],
            "selector": data["selector"],
            "confidence": data.get("confidence", 0.5),
        }
    except Exception as exc:
        logger.warning("AI locator request failed: {}", exc)
        return None

