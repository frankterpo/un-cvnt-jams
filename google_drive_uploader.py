"""
Google Drive Uploader using Service Account
Uploads files to specific Google Drive folders
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
from config import SERVICE_ACCOUNT_FILE, GDRIVE_FOLDERS


class GoogleDriveUploader:
    def __init__(self, use_mock: bool = True):
        self.service_account_file = SERVICE_ACCOUNT_FILE
        self.folders = GDRIVE_FOLDERS.copy()
        self.use_mock = use_mock

        # Initialize Google Drive API client with shared drives support
        if not self.use_mock:
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    self.service_account_file,
                    scopes=['https://www.googleapis.com/auth/drive']
                )
                self.service = build('drive', 'v3', credentials=credentials)
                print("✅ Google Drive API client initialized (shared drives enabled)")
            except Exception as e:
                print(f"❌ Google Drive client initialization failed: {e}")
                print("⚠️ Falling back to mock uploads")
                self.use_mock = True
        else:
            self.service = None
            print("🎭 Using mock Google Drive uploads (service account not fully configured)")

    def upload_file(self, file_path: str, folder_name: str, job_id: str, video_id: str = None) -> Dict[str, Any]:
        """
        Upload a file to Google Drive in the specified folder
        """
        file_path = Path(file_path)
        if not file_path.exists():
            return {"error": f"File not found: {file_path}"}

        # Get folder ID
        folder_id = self.folders.get(folder_name)
        if not folder_id:
            return {"error": f"Unknown folder name: {folder_name}"}

        # Create filename with job ID
        original_name = file_path.name
        if video_id:
            new_filename = f"{job_id}_{video_id}_{original_name}"
        else:
            new_filename = f"{job_id}_{original_name}"

        print(f"☁️ Uploading {original_name} to Google Drive folder: {folder_name}")

        if self.use_mock:
            return self._mock_upload_file(file_path, folder_name, folder_id, job_id, video_id, new_filename)

        try:
            # Prepare file metadata
            file_metadata = {
                'name': new_filename,
                'parents': [folder_id]
            }

            # Prepare media upload
            media = MediaFileUpload(
                str(file_path),
                resumable=True,
                chunksize=1024*1024  # 1MB chunks
            )

            # Upload file to shared drive
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,webViewLink,size,mimeType',
                supportsAllDrives=True  # Enable shared drives support
            ).execute()

            result = {
                "job_id": job_id,
                "video_id": video_id,
                "folder_name": folder_name,
                "folder_id": folder_id,
                "file_id": file.get('id'),
                "file_name": file.get('name'),
                "file_size": file.get('size'),
                "mime_type": file.get('mimeType'),
                "web_view_link": file.get('webViewLink'),
                "local_path": str(file_path),
                "upload_success": True
            }

            file_size_mb = int(file.get('size', 0)) / (1024 * 1024)
            print(f"✅ Uploaded: {new_filename} ({file_size_mb:.1f}MB) - {file.get('webViewLink')}")

            return result

        except Exception as e:
            error_msg = f"Upload failed: {str(e)}"
            print(f"❌ {error_msg}")

            return {
                "job_id": job_id,
                "video_id": video_id,
                "folder_name": folder_name,
                "local_path": str(file_path),
                "error": error_msg,
                "upload_success": False
            }

    def _mock_upload_file(self, file_path: Path, folder_name: str, folder_id: str,
                         job_id: str, video_id: str, new_filename: str) -> Dict[str, Any]:
        """Mock upload for testing when Drive API is not fully configured"""
        print("🎭 Mock uploading (simulating Google Drive upload)")

        # Get file info
        file_size = file_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)

        # Generate mock Google Drive file ID and URL
        import uuid
        mock_file_id = str(uuid.uuid4())[:8]

        # Mock web view link (would be actual Google Drive link)
        mock_web_link = f"https://drive.google.com/file/d/{mock_file_id}/view"

        result = {
            "job_id": job_id,
            "video_id": video_id,
            "folder_name": folder_name,
            "folder_id": folder_id,
            "file_id": mock_file_id,
            "file_name": new_filename,
            "file_size": str(file_size),
            "mime_type": self._guess_mime_type(file_path),
            "web_view_link": mock_web_link,
            "local_path": str(file_path),
            "upload_success": True,
            "mock_upload": True
        }

        print(f"✅ Mock uploaded: {new_filename} ({file_size_mb:.1f}MB) - {mock_web_link}")
        return result

    def _guess_mime_type(self, file_path: Path) -> str:
        """Guess MIME type based on file extension"""
        ext = file_path.suffix.lower()
        mime_types = {
            '.mp4': 'video/mp4',
            '.mp3': 'audio/mpeg',
            '.json': 'application/json',
            '.wav': 'audio/wav',
            '.jpg': 'image/jpeg',
            '.png': 'image/png'
        }
        return mime_types.get(ext, 'application/octet-stream')

    def batch_upload(self, files_to_upload: List[Dict[str, str]], job_id: str) -> List[Dict[str, Any]]:
        """
        Upload multiple files to appropriate Google Drive folders
        files_to_upload should contain: 'file_path', 'folder_name', 'video_id' (optional)
        """
        results = []

        for file_info in files_to_upload:
            file_path = file_info.get('file_path')
            folder_name = file_info.get('folder_name')
            video_id = file_info.get('video_id')

            if not file_path or not folder_name:
                results.append({
                    "error": "Missing file_path or folder_name",
                    "file_info": file_info
                })
                continue

            try:
                result = self.upload_file(file_path, folder_name, job_id, video_id)
                results.append(result)
            except Exception as e:
                print(f"❌ Batch upload failed for {file_path}: {e}")
                results.append({
                    "file_path": file_path,
                    "folder_name": folder_name,
                    "video_id": video_id,
                    "error": str(e),
                    "upload_success": False
                })

        return results

    def upload_job_assets(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upload all assets for a job to appropriate Google Drive folders
        """
        job_id = job_data.get('job_id')
        if not job_id:
            return {"error": "No job_id provided"}

        print(f"📤 Uploading all assets for job: {job_id}")

        files_to_upload = []
        upload_results = {}

        # Upload video file
        if job_data.get('video_path'):
            files_to_upload.append({
                'file_path': job_data['video_path'],
                'folder_name': 'video',
                'video_id': job_data.get('video_id')
            })

        # Upload audio file
        if job_data.get('audio_path'):
            files_to_upload.append({
                'file_path': job_data['audio_path'],
                'folder_name': 'audio',
                'video_id': job_data.get('video_id')
            })

        # Upload transcription file
        if job_data.get('transcript_path'):
            files_to_upload.append({
                'file_path': job_data['transcript_path'],
                'folder_name': 'transcription',
                'video_id': job_data.get('video_id')
            })

        # Note: Music files would be uploaded separately when available

        # Perform batch upload
        upload_results = self.batch_upload(files_to_upload, job_id)

        # Summarize results
        successful = [r for r in upload_results if r.get('upload_success')]
        failed = [r for r in upload_results if not r.get('upload_success')]

        summary = {
            "job_id": job_id,
            "total_files": len(upload_results),
            "successful_uploads": len(successful),
            "failed_uploads": len(failed),
            "upload_results": upload_results,
            "gdrive_links": {r.get('file_name', 'unknown'): r.get('web_view_link') for r in successful}
        }

        print(f"📊 Upload summary: {len(successful)}/{len(upload_results)} files uploaded successfully")
        return summary

    def list_folder_contents(self, folder_name: str) -> List[Dict[str, Any]]:
        """List contents of a specific Google Drive folder"""
        if not self.service:
            return []

        folder_id = self.folders.get(folder_name)
        if not folder_id:
            print(f"❌ Unknown folder: {folder_name}")
            return []

        try:
            results = self.service.files().list(
                q=f"'{folder_id}' in parents",
                fields="files(id,name,size,mimeType,webViewLink,createdTime)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()

            files = results.get('files', [])
            print(f"📁 Folder '{folder_name}' contains {len(files)} files")
            return files

        except Exception as e:
            print(f"❌ Failed to list folder contents: {e}")
            return []

    def get_upload_stats(self) -> Dict[str, Any]:
        """Get upload statistics for all folders"""
        stats = {}

        for folder_name in self.folders.keys():
            contents = self.list_folder_contents(folder_name)
            total_size = sum(int(f.get('size', 0)) for f in contents)

            stats[folder_name] = {
                "file_count": len(contents),
                "total_size_mb": round(total_size / (1024 * 1024), 1),
                "folder_id": self.folders[folder_name]
            }

        return stats


def test_uploader():
    """Test the Google Drive uploader"""
    uploader = GoogleDriveUploader(use_mock=True)  # Force mock mode for testing

    # Test with a small file (use the transcript we just created)
    from config import TRANSCRIPTS_DIR
    test_files = list(TRANSCRIPTS_DIR.glob("*test_transcript*.json"))

    if not test_files:
        print("❌ No test files found for upload test")
        return

    test_file = test_files[0]
    print(f"🧪 Testing upload with: {test_file.name}")

    result = uploader.upload_file(str(test_file), "transcription", "test_upload", "19peKG-nkcs")

    print(f"📊 Upload test result: {json.dumps(result, indent=2)}")

    # Show folder stats (only works with real service)
    if uploader.service and not uploader.use_mock:
        stats = uploader.get_upload_stats()
        print(f"📈 Drive stats: {json.dumps(stats, indent=2)}")
    else:
        print("📈 Folder stats: Mock mode - showing configured folders")
        print(f"📁 Configured folders: {list(uploader.folders.keys())}")


if __name__ == "__main__":
    test_uploader()
