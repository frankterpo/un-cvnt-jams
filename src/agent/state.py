"""State management for upload idempotency."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class UploadRecord:
    """Record of an upload attempt."""

    drive_file_id: str
    platform: str  # "tiktok", "youtube", "instagram"
    status: str  # "success" | "failed"
    last_updated: datetime

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "drive_file_id": self.drive_file_id,
            "platform": self.platform,
            "status": self.status,
            "last_updated": self.last_updated.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> UploadRecord:
        """Create from dictionary."""
        return cls(
            drive_file_id=data["drive_file_id"],
            platform=data["platform"],
            status=data["status"],
            last_updated=datetime.fromisoformat(data["last_updated"]),
        )


class UploadState:
    """Simple file-based state store for upload records."""

    def __init__(self, state_file: Path | None = None):
        """Initialize state store."""
        default_path = Path(os.getenv("UPLOAD_STATE_PATH", "pipeline_output/upload_state.json")).expanduser()
        self.state_file = state_file or default_path
        self.records: list[UploadRecord] = []
        self._load()

    @classmethod
    def load_default(cls) -> UploadState:
        """Load the default state file."""
        return cls()

    def _load(self) -> None:
        """Load state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    self.records = [UploadRecord.from_dict(r) for r in data]
            except Exception:
                self.records = []
        else:
            self.records = []

    def save(self) -> None:
        """Save state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump([r.to_dict() for r in self.records], f, indent=2)

    def _save(self) -> None:
        """Backward-compatible alias for save()."""
        self.save()

    def has_successful_upload(self, drive_file_id: str, platform: str) -> bool:
        """Check if a successful upload exists for a drive file and platform."""
        for record in self.records:
            if (
                record.drive_file_id == drive_file_id
                and record.platform == platform
                and record.status == "success"
            ):
                return True
        return False

    def has_success(self, drive_file_id: str, platform: str) -> bool:
        """Alias for has_successful_upload for convenience."""
        return self.has_successful_upload(drive_file_id, platform)

    def record_upload(
        self,
        drive_file_id: str,
        platform: str,
        status: str,
    ) -> None:
        """Record an upload attempt."""
        # Remove any existing record for this file/platform
        self.records = [
            r
            for r in self.records
            if not (r.drive_file_id == drive_file_id and r.platform == platform)
        ]

        # Add new record
        record = UploadRecord(
            drive_file_id=drive_file_id,
            platform=platform,
            status=status,
            last_updated=datetime.now(),
        )
        self.records.append(record)
        self._save()

    def mark_success(self, drive_file_id: str, platform: str) -> None:
        """Record a successful upload."""
        self.record_upload(drive_file_id, platform, "success")

    def mark_failed(self, drive_file_id: str, platform: str) -> None:
        """Record a failed upload."""
        self.record_upload(drive_file_id, platform, "failed")

    def has_all_success(self, drive_file_id: str) -> bool:
        """Return True if all known platform entries for this id are successful."""
        statuses = [r.status for r in self.records if r.drive_file_id == drive_file_id]
        return bool(statuses) and all(s == "success" for s in statuses)

