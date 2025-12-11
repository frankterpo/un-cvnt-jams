"""YouTube metadata models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class YouTubeMetadata(BaseModel):
    """Metadata for YouTube video uploads."""

    title: str
    description: str
    tags: list[str] = []
    publish_at: datetime | None = None  # None => publish immediately

