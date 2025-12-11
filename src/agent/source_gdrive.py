"""Google Drive source helpers -> VideoItem list."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Callable, Dict, List

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from agent.workflow import VideoItem
from agent.state import UploadState


def build_drive_client(sa_json_path: Path):
    """Build a Google Drive service client from a service account JSON file."""
    creds = Credentials.from_service_account_file(str(sa_json_path))
    return build("drive", "v3", credentials=creds)


def list_videos_in_folder(service, folder_id: str) -> List[Dict[str, Any]]:
    """List video files in a given folder (single page)."""
    q = f"'{folder_id}' in parents and mimeType contains 'video/' and trashed = false"
    res = service.files().list(q=q, fields="files(id,name,mimeType)").execute()
    return res.get("files", [])


def download_video(service, file_id: str, dest: Path) -> Path:
    """Download a single video file to dest."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(dest, "wb")
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return dest


def build_items_from_folder(
    service,
    folder_id: str,
    download_dir: Path,
    caption_fn: Callable[[str], Dict[str, Any]],
    state: UploadState | None = None,
) -> list[VideoItem]:
    """
    Build VideoItem objects for all videos in a Drive folder.

    - Uses file.id as the stable VideoItem.id.
    - Optionally skips files fully processed if `state` is provided and has_all_success returns True.
    """
    items: list[VideoItem] = []
    files = list_videos_in_folder(service, folder_id)

    for f in files:
        file_id = f["id"]
        name = f["name"]

        if state is not None and state.has_all_success(file_id):
            continue

        local_path = download_video(service, file_id, download_dir / name)
        captions = caption_fn(name)
        items.append(VideoItem(id=file_id, path=local_path, captions=captions))

    return items

