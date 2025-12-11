"""Caption generation stubs (replace with LLM later)."""

from __future__ import annotations

from typing import Any, Dict


def generate_captions_from_title(title: str) -> Dict[str, Any]:
    """Minimal placeholder for captions."""
    base = title.strip() or "New video"
    return {
        "tiktok": f"{base} #shorts",
        "youtube": {
            "title": base,
            "description": f"{base}\n\nUploaded via social agent.",
            "tags": [],
            "publish_at": None,
        },
        "instagram": f"{base} #reel",
    }

