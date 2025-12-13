#!/usr/bin/env python3
"""Verify Google Drive Access."""

import sys
import os
from pathlib import Path
from loguru import logger

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent.source_gdrive import build_drive_client

def test_access():
    logger.info("Testing Google Drive Access...")
    
    sa_json = os.getenv("GDRIVE_SA_JSON", "blissful-fiber-473419-e6-abf91b637595.json")
    if not os.path.exists(sa_json):
        logger.error(f"Service account file not found: {sa_json}")
        return

    try:
        service = build_drive_client(Path(sa_json))
        
        # Try to list files to verify permission/api working
        # Query for a 'test' folder or just list 1 file
        results = service.files().list(
            pageSize=1, 
            fields="nextPageToken, files(id, name)"
        ).execute()
        items = results.get('files', [])

        logger.success("Successfully connected to Google Drive API!")
        if not items:
            logger.warning("No files found visible to this service account.")
        else:
            logger.info(f"Found {len(items)} file(s) as sample: {items}")
            
    except Exception as e:
        logger.exception("Failed to connect to Google Drive.")

if __name__ == "__main__":
    test_access()
