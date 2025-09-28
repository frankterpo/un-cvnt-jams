"""
Media Downloader Module using yt-dlp
Downloads .mp4 and .mp3 files from YouTube videos
"""

import os
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from config import DOWNLOADS_DIR, YTDLP_CONFIG


class MediaDownloader:
    def __init__(self):
        self.downloads_dir = DOWNLOADS_DIR
        self.ytdlp_config = YTDLP_CONFIG.copy()

    def download_video_and_audio(self, video_id: str, job_id: str) -> Dict[str, str]:
        """
        Download both .mp4 video and .mp3 audio for a YouTube video
        Returns dict with file paths
        """
        print(f"📥 Downloading media for video: {video_id} (Job: {job_id})")

        video_url = f"https://www.youtube.com/watch?v={video_id}"

        # Download MP4 video
        video_path = self._download_mp4(video_url, video_id, job_id)

        # Download MP3 audio
        audio_path = self._download_mp3(video_url, video_id, job_id)

        result = {
            "video_id": video_id,
            "job_id": job_id,
            "video_path": str(video_path) if video_path else None,
            "audio_path": str(audio_path) if audio_path else None,
            "url": video_url
        }

        print(f"✅ Download complete: MP4={bool(video_path)}, MP3={bool(audio_path)}")
        return result

    def _download_mp4(self, url: str, video_id: str, job_id: str) -> Optional[Path]:
        """Download MP4 video file"""
        output_template = str(self.downloads_dir / f"{job_id}_{video_id}.mp4")

        cmd = [
            "yt-dlp",
            "--format", "best[height<=720]",  # Good quality but not too large
            "--output", output_template,
            "--no-playlist",
            "--quiet",
            "--no-warnings",
            url
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                output_path = Path(output_template)
                if output_path.exists():
                    file_size = output_path.stat().st_size / (1024 * 1024)  # MB
                    print(f"📼 MP4 downloaded: {output_path.name} ({file_size:.1f}MB)")
                    return output_path
            else:
                print(f"❌ MP4 download failed: {result.stderr}")
                return None
        except subprocess.TimeoutExpired:
            print(f"⏰ MP4 download timed out for {video_id}")
            return None
        except Exception as e:
            print(f"❌ MP4 download error: {e}")
            return None

    def _download_mp3(self, url: str, video_id: str, job_id: str) -> Optional[Path]:
        """Download MP3 audio file"""
        output_template = str(self.downloads_dir / f"{job_id}_{video_id}.mp3")

        cmd = [
            "yt-dlp",
            "--format", "bestaudio/best",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "128K",  # Good quality audio
            "--output", output_template,
            "--no-playlist",
            "--quiet",
            "--no-warnings",
            url
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                output_path = Path(output_template)
                if output_path.exists():
                    file_size = output_path.stat().st_size / (1024 * 1024)  # MB
                    print(f"🎵 MP3 downloaded: {output_path.name} ({file_size:.1f}MB)")
                    return output_path
            else:
                print(f"❌ MP3 download failed: {result.stderr}")
                return None
        except subprocess.TimeoutExpired:
            print(f"⏰ MP3 download timed out for {video_id}")
            return None
        except Exception as e:
            print(f"❌ MP3 download error: {e}")
            return None

    def batch_download(self, video_data: List[Dict[str, str]], job_id: str) -> List[Dict[str, str]]:
        """
        Download media for multiple videos
        video_data should contain 'video_id' keys
        """
        results = []

        for video_info in video_data:
            video_id = video_info["video_id"]
            try:
                result = self.download_video_and_audio(video_id, job_id)
                results.append(result)
            except Exception as e:
                print(f"❌ Failed to download {video_id}: {e}")
                results.append({
                    "video_id": video_id,
                    "job_id": job_id,
                    "error": str(e),
                    "video_path": None,
                    "audio_path": None
                })

        return results

    def cleanup_old_files(self, days_old: int = 7):
        """Clean up downloaded files older than specified days"""
        import time

        cutoff_time = time.time() - (days_old * 24 * 60 * 60)

        for file_path in self.downloads_dir.glob("*"):
            if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                file_path.unlink()
                print(f"🗑️ Cleaned up old file: {file_path.name}")

    def get_download_stats(self) -> Dict[str, int]:
        """Get statistics about downloaded files"""
        mp4_count = len(list(self.downloads_dir.glob("*.mp4")))
        mp3_count = len(list(self.downloads_dir.glob("*.mp3")))

        total_size = 0
        for file_path in self.downloads_dir.glob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size

        return {
            "mp4_files": mp4_count,
            "mp3_files": mp3_count,
            "total_files": mp4_count + mp3_count,
            "total_size_mb": round(total_size / (1024 * 1024), 1)
        }


def test_downloader():
    """Test the media downloader with a sample video"""
    downloader = MediaDownloader()

    # Test with a known Scooby Doo short
    test_video_id = "19peKG-nkcs"  # One we found earlier
    test_job_id = "test_001"

    print("🧪 Testing media downloader...")
    result = downloader.download_video_and_audio(test_video_id, test_job_id)

    print(f"📊 Test result: {json.dumps(result, indent=2)}")

    # Show download stats
    stats = downloader.get_download_stats()
    print(f"📈 Download stats: {json.dumps(stats, indent=2)}")


if __name__ == "__main__":
    test_downloader()
