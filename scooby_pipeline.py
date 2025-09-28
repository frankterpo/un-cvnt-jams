#!/usr/bin/env python3
"""
Scooby Doo Pipeline Orchestrator
Complete pipeline: YouTube → Download → Transcribe → Upload → Shotstack → Render
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# Import all pipeline components
from config import OUTPUT_DIR
from youtube_search import YouTubeSearcher
from media_downloader import MediaDownloader
from speech_transcriber import SpeechTranscriber
from google_drive_uploader import GoogleDriveUploader
from job_tracker import JobTracker
from shotstack_client import ShotstackClient


class ScoobyPipeline:
    def __init__(self, use_mock_services: bool = True):
        """
        Initialize the complete Scooby Doo pipeline
        """
        self.use_mock = use_mock_services

        # Initialize all components
        self.youtube_searcher = YouTubeSearcher()
        self.media_downloader = MediaDownloader()
        self.speech_transcriber = SpeechTranscriber(use_mock=self.use_mock)
        self.drive_uploader = GoogleDriveUploader(use_mock=self.use_mock)
        self.job_tracker = JobTracker()
        self.shotstack_client = ShotstackClient()

        print("🎭 Scooby Doo Pipeline initialized" + (" (MOCK MODE)" if self.use_mock else ""))

    def run_pipeline(self, max_videos: int = 3) -> Dict[str, Any]:
        """
        Run the complete Scooby Doo pipeline
        """
        # Validate max_videos parameter
        if max_videos < 1 or max_videos > 50:
            raise ValueError("max_videos must be between 1 and 50")

        print(f"🚀 Starting Scooby Doo Pipeline (processing up to {max_videos} videos)...")

        # Step 1: Create job
        job_id = self.job_tracker.create_job("scooby_pipeline", {"max_videos": max_videos})
        print(f"📋 Job created: {job_id}")

        try:
            # Step 2: Search YouTube for Scooby Doo shorts
            print("\n🎥 Step 1: Searching YouTube for Scooby Doo shorts...")
            self.job_tracker.update_job_step(job_id, "youtube_search", "running")

            shorts_data = self.youtube_searcher.search_scooby_shorts_advanced()

            # Additional deduplication: Check if we've processed these videos in recent jobs
            processed_video_ids = self._get_recently_processed_video_ids()
            unique_shorts = []
            for short in shorts_data:
                if short["video_id"] not in processed_video_ids:
                    unique_shorts.append(short)
                else:
                    print(f"⏭️ Skipping already processed video: {short['video_id']} ({short['title'][:30]}...)")

            shorts_data = unique_shorts[:max_videos]  # Limit videos after deduplication

            if len(shorts_data) < max_videos:
                print(f"⚠️ Only found {len(shorts_data)} new videos (some were previously processed)")

            self.job_tracker.update_job_step(job_id, "youtube_search", "completed", {
                "videos_found": len(shorts_data),
                "videos_requested": max_videos,
                "videos": [{"video_id": v["video_id"], "title": v["title"], "url_short": v["url_short"]} for v in shorts_data]
            })

            if not shorts_data:
                raise Exception("No Scooby Doo shorts found")

            print(f"✅ Found {len(shorts_data)} Scooby Doo shorts")

            # Step 3: Download media (MP4 + MP3)
            print("\n📥 Step 2: Downloading media files...")
            self.job_tracker.update_job_step(job_id, "media_download", "running")

            download_results = self.media_downloader.batch_download(shorts_data, job_id)

            successful_downloads = [r for r in download_results if r.get("video_path") and r.get("audio_path")]
            failed_downloads = [r for r in download_results if not r.get("video_path") or not r.get("audio_path")]

            self.job_tracker.update_job_step(job_id, "media_download", "completed", {
                "total_downloads": len(download_results),
                "successful": len(successful_downloads),
                "failed": len(failed_downloads),
                "downloads": download_results
            })

            print(f"✅ Downloaded media for {len(successful_downloads)}/{len(download_results)} videos")

            # Step 4: Transcribe audio files
            print("\n🎙️ Step 3: Transcribing audio files...")
            self.job_tracker.update_job_step(job_id, "transcription", "running")

            audio_files = [{"audio_path": r["audio_path"], "video_id": r["video_id"]} for r in successful_downloads]
            transcription_results = self.speech_transcriber.batch_transcribe(audio_files, job_id)

            successful_transcripts = [r for r in transcription_results if r.get("transcription")]
            failed_transcripts = [r for r in transcription_results if not r.get("transcription")]

            self.job_tracker.update_job_step(job_id, "transcription", "completed", {
                "total_transcriptions": len(transcription_results),
                "successful": len(successful_transcripts),
                "failed": len(failed_transcripts),
                "transcriptions": transcription_results
            })

            print(f"✅ Transcribed {len(successful_transcripts)}/{len(transcription_results)} audio files")

            # Step 5: Upload to Google Drive
            print("\n☁️ Step 4: Uploading assets to Google Drive...")
            self.job_tracker.update_job_step(job_id, "drive_upload", "running")

            # Prepare files for upload
            files_to_upload = []

            # Add video files
            for result in successful_downloads:
                if result.get("video_path"):
                    files_to_upload.append({
                        "file_path": result["video_path"],
                        "folder_name": "video",
                        "video_id": result["video_id"]
                    })

            # Add audio files
            for result in successful_downloads:
                if result.get("audio_path"):
                    files_to_upload.append({
                        "file_path": result["audio_path"],
                        "folder_name": "audio",
                        "video_id": result["video_id"]
                    })

            # Add transcription files
            for result in successful_transcripts:
                if result.get("transcript_path"):
                    files_to_upload.append({
                        "file_path": result["transcript_path"],
                        "folder_name": "transcription",
                        "video_id": result["video_id"]
                    })

            upload_results = self.drive_uploader.batch_upload(files_to_upload, job_id)

            successful_uploads = [r for r in upload_results if r.get("upload_success")]
            failed_uploads = [r for r in upload_results if not r.get("upload_success")]

            self.job_tracker.update_job_step(job_id, "drive_upload", "completed", {
                "total_uploads": len(upload_results),
                "successful": len(successful_uploads),
                "failed": len(failed_uploads),
                "uploads": upload_results
            })

            print(f"✅ Uploaded {len(successful_uploads)}/{len(upload_results)} files to Google Drive")

            # Step 6: Create Shotstack timeline
            print("\n🎬 Step 5: Creating Shotstack timeline...")
            self.job_tracker.update_job_step(job_id, "shotstack_render", "running")

            # Prepare assets for timeline
            video_assets = []
            audio_assets = []
            transcript_data = None

            # Collect video assets with Drive links
            for upload in successful_uploads:
                if upload.get("folder_name") == "video":
                    video_asset = next((v for v in shorts_data if v["video_id"] == upload["video_id"]), None)
                    if video_asset:
                        video_asset_copy = video_asset.copy()
                        video_asset_copy.update({
                            "web_view_link": upload.get("web_view_link"),
                            "file_id": upload.get("file_id")
                        })
                        video_assets.append(video_asset_copy)

            # Collect audio assets
            for upload in successful_uploads:
                if upload.get("folder_name") == "audio":
                    audio_assets.append({
                        "video_id": upload["video_id"],
                        "web_view_link": upload.get("web_view_link"),
                        "file_id": upload.get("file_id"),
                        "duration_seconds": 15.0  # Default duration
                    })

            # Use first transcript for subtitles
            if successful_transcripts:
                transcript_data = successful_transcripts[0].get("transcription")

            # Create timeline
            timeline_result = self.shotstack_client.create_scooby_timeline(
                job_id, video_assets, audio_assets, transcript_data
            )

            # Submit for rendering
            render_result = self.shotstack_client.render_timeline(timeline_result)

            self.job_tracker.update_job_step(job_id, "shotstack_render", "completed", {
                "timeline_created": True,
                "render_submitted": True,
                "timeline_file": timeline_result["timeline_file"],
                "render_id": render_result["render_id"],
                "estimated_duration": timeline_result["estimated_duration"]
            })

            print(f"✅ Timeline created and render submitted: {render_result['render_id']}")

            # Get final job summary
            job_summary = self.job_tracker.get_job_summary(job_id)

            print("\n🎉 Pipeline completed successfully!")
            print(f"📊 Final Summary: {json.dumps(job_summary, indent=2)}")

            return {
                "success": True,
                "job_id": job_id,
                "job_summary": job_summary,
                "timeline_result": timeline_result,
                "render_result": render_result
            }

        except Exception as e:
            error_msg = f"Pipeline failed: {str(e)}"
            print(f"❌ {error_msg}")

            # Update job with failure
            self.job_tracker.update_job_step(job_id, "youtube_search", "failed", {"error": error_msg})

            return {
                "success": False,
                "job_id": job_id,
                "error": error_msg
            }

    def _get_recently_processed_video_ids(self, days_back: int = 7) -> set:
        """Get video IDs that have been processed in recent jobs to avoid duplicates"""
        import time
        from datetime import datetime, timedelta

        cutoff_time = datetime.now() - timedelta(days=days_back)
        processed_ids = set()

        # Get recent completed jobs
        recent_jobs = self.job_tracker.list_jobs("completed")

        for job in recent_jobs:
            try:
                job_created = datetime.fromisoformat(job["created_at"].replace('Z', '+00:00'))
                if job_created >= cutoff_time:
                    # Load job details to get processed video IDs
                    job_details = self.job_tracker.load_job(job["job_id"])
                    if job_details and "steps" in job_details:
                        search_step = job_details["steps"].get("youtube_search", {})
                        if search_step.get("status") == "completed" and "data" in search_step:
                            videos = search_step["data"].get("videos", [])
                            for video in videos:
                                if isinstance(video, dict) and "id" in video:
                                    processed_ids.add(video["id"])
            except (ValueError, KeyError) as e:
                # Skip jobs with invalid data
                continue

        return processed_ids

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a pipeline job"""
        return self.job_tracker.get_job_summary(job_id)

    def list_jobs(self, status_filter: str = None) -> List[Dict[str, Any]]:
        """List all pipeline jobs"""
        return self.job_tracker.list_jobs(status_filter)


def main():
    """Main entry point for the Scooby Doo pipeline"""
    import argparse

    parser = argparse.ArgumentParser(description="Scooby Doo Video Pipeline")
    parser.add_argument("--max-videos", "-n", type=int, default=3,
                        help="Maximum videos to process (1-50, default: 3)",
                        metavar="NUM", choices=range(1, 51))
    parser.add_argument("--mock", action="store_true", help="Use mock services for testing")
    parser.add_argument("--real", action="store_true", help="Use real services (requires API keys)")
    parser.add_argument("--job-id", help="Check status of specific job")
    parser.add_argument("--list-jobs", action="store_true", help="List all jobs")

    args = parser.parse_args()

    # Determine if we should use mock services
    # Default to mock mode, use real only if explicitly requested
    use_mock = not args.real

    pipeline = ScoobyPipeline(use_mock_services=use_mock)

    if args.list_jobs:
        jobs = pipeline.list_jobs()
        print(f"📋 Found {len(jobs)} jobs:")
        for job in jobs:
            print(f"  - {job['job_id']}: {job['status']} ({job['created_at']})")
        return

    if args.job_id:
        status = pipeline.get_job_status(args.job_id)
        if status:
            print(f"📊 Job Status for {args.job_id}:")
            print(json.dumps(status, indent=2))
        else:
            print(f"❌ Job not found: {args.job_id}")
        return

    # Run the pipeline
    result = pipeline.run_pipeline(max_videos=args.max_videos)

    if result["success"]:
        print("\n✅ Pipeline completed successfully!")
        print(f"🎬 Final video will be available at: [Shotstack render URL]")
    else:
        print(f"\n❌ Pipeline failed: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
