"""
Job Tracker Module
Creates and manages unique job IDs for tracking pipeline execution
"""

import uuid
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from config import OUTPUT_DIR


class JobTracker:
    def __init__(self):
        self.jobs_dir = OUTPUT_DIR / "jobs"
        self.jobs_dir.mkdir(exist_ok=True)
        self.active_jobs = {}

    def create_job(self, job_type: str = "scooby_pipeline", metadata: Dict[str, Any] = None) -> str:
        """
        Create a new job with unique ID
        """
        job_id = self._generate_job_id()
        timestamp = datetime.now().isoformat()

        job_data = {
            "job_id": job_id,
            "job_type": job_type,
            "created_at": timestamp,
            "status": "created",
            "metadata": metadata or {},
            "steps": {
                "youtube_search": {"status": "pending", "timestamp": None, "data": None},
                "media_download": {"status": "pending", "timestamp": None, "data": None},
                "transcription": {"status": "pending", "timestamp": None, "data": None},
                "drive_upload": {"status": "pending", "timestamp": None, "data": None},
                "shotstack_render": {"status": "pending", "timestamp": None, "data": None}
            },
            "assets": {
                "videos": [],
                "audios": [],
                "transcripts": [],
                "uploads": [],
                "shotstack_renders": []
            }
        }

        # Save job file
        self._save_job(job_data)

        # Track active job
        self.active_jobs[job_id] = job_data

        print(f"🆔 Created job: {job_id} ({job_type})")
        return job_id

    def _generate_job_id(self) -> str:
        """Generate a unique job ID"""
        # Format: scooby_YYYYMMDD_HHMMSS_XXXX
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_part = str(uuid.uuid4())[:4]  # First 4 chars of UUID
        return f"scooby_{timestamp}_{unique_part}"

    def _save_job(self, job_data: Dict[str, Any]):
        """Save job data to file"""
        job_id = job_data["job_id"]
        job_file = self.jobs_dir / f"{job_id}.json"

        with open(job_file, "w") as f:
            json.dump(job_data, f, indent=2, default=str)

    def load_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Load job data from file"""
        job_file = self.jobs_dir / f"{job_id}.json"

        if not job_file.exists():
            print(f"❌ Job not found: {job_id}")
            return None

        with open(job_file, "r") as f:
            job_data = json.load(f)

        self.active_jobs[job_id] = job_data
        return job_data

    def update_job_step(self, job_id: str, step_name: str, status: str, data: Any = None):
        """
        Update the status of a job step
        """
        job_data = self.load_job(job_id)
        if not job_data:
            return

        if step_name not in job_data["steps"]:
            print(f"⚠️ Unknown step: {step_name}")
            return

        timestamp = datetime.now().isoformat()
        job_data["steps"][step_name] = {
            "status": status,
            "timestamp": timestamp,
            "data": data
        }

        # Update overall job status
        job_data["updated_at"] = timestamp
        all_steps = list(job_data["steps"].values())
        if all(step["status"] == "completed" for step in all_steps):
            job_data["status"] = "completed"
        elif any(step["status"] == "failed" for step in all_steps):
            job_data["status"] = "failed"
        elif any(step["status"] == "running" for step in all_steps):
            job_data["status"] = "running"
        else:
            job_data["status"] = "in_progress"

        self._save_job(job_data)
        print(f"📝 Updated job {job_id} step '{step_name}' to '{status}'")

    def add_asset(self, job_id: str, asset_type: str, asset_data: Dict[str, Any]):
        """
        Add an asset to the job tracking
        """
        job_data = self.load_job(job_id)
        if not job_data:
            return

        if asset_type not in job_data["assets"]:
            print(f"⚠️ Unknown asset type: {asset_type}")
            return

        job_data["assets"][asset_type].append(asset_data)
        job_data["updated_at"] = datetime.now().isoformat()

        self._save_job(job_data)
        print(f"📎 Added {asset_type} asset to job {job_id}")

    def get_job_summary(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a summary of job progress"""
        job_data = self.load_job(job_id)
        if not job_data:
            return None

        steps_completed = sum(1 for step in job_data["steps"].values() if step["status"] == "completed")
        total_steps = len(job_data["steps"])

        assets_count = {asset_type: len(assets) for asset_type, assets in job_data["assets"].items()}

        return {
            "job_id": job_id,
            "status": job_data["status"],
            "progress": f"{steps_completed}/{total_steps} steps completed",
            "created_at": job_data["created_at"],
            "assets": assets_count,
            "steps_status": {step: data["status"] for step, data in job_data["steps"].items()}
        }

    def list_jobs(self, status_filter: str = None) -> List[Dict[str, Any]]:
        """List all jobs, optionally filtered by status"""
        jobs = []

        for job_file in self.jobs_dir.glob("*.json"):
            try:
                with open(job_file, "r") as f:
                    job_data = json.load(f)

                if status_filter and job_data.get("status") != status_filter:
                    continue

                jobs.append({
                    "job_id": job_data["job_id"],
                    "status": job_data["status"],
                    "created_at": job_data["created_at"],
                    "job_type": job_data.get("job_type", "unknown")
                })
            except Exception as e:
                print(f"⚠️ Error reading job file {job_file}: {e}")

        # Sort by creation time (newest first)
        jobs.sort(key=lambda x: x["created_at"], reverse=True)
        return jobs

    def cleanup_old_jobs(self, days_old: int = 30):
        """Clean up job files older than specified days"""
        cutoff_time = time.time() - (days_old * 24 * 60 * 60)

        cleaned = 0
        for job_file in self.jobs_dir.glob("*.json"):
            if job_file.stat().st_mtime < cutoff_time:
                job_file.unlink()
                cleaned += 1

        if cleaned > 0:
            print(f"🗑️ Cleaned up {cleaned} old job files")


def test_job_tracker():
    """Test the job tracking functionality"""
    tracker = JobTracker()

    # Create a test job
    job_id = tracker.create_job("test_pipeline", {"test": True})
    print(f"✅ Created test job: {job_id}")

    # Update some steps
    tracker.update_job_step(job_id, "youtube_search", "completed", {"videos_found": 5})
    tracker.update_job_step(job_id, "media_download", "running")

    # Add some assets
    tracker.add_asset(job_id, "videos", {"video_id": "test123", "path": "/tmp/test.mp4"})
    tracker.add_asset(job_id, "audios", {"video_id": "test123", "path": "/tmp/test.mp3"})

    # Get summary
    summary = tracker.get_job_summary(job_id)
    print(f"📊 Job summary: {json.dumps(summary, indent=2)}")

    # List all jobs
    all_jobs = tracker.list_jobs()
    print(f"📋 Total jobs: {len(all_jobs)}")
    for job in all_jobs[:3]:  # Show first 3
        print(f"  - {job['job_id']}: {job['status']} ({job['created_at']})")


if __name__ == "__main__":
    test_job_tracker()
