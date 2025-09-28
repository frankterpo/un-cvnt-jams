"""
Shotstack MCP Client
Creates video timelines using Shotstack API via MCP
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from config import OUTPUT_DIR


class ShotstackClient:
    def __init__(self):
        self.shotstack_dir = OUTPUT_DIR / "shotstack"
        self.shotstack_dir.mkdir(exist_ok=True)

    def create_scooby_timeline(self, job_id: str, video_assets: List[Dict[str, Any]],
                              audio_assets: List[Dict[str, Any]],
                              transcript_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create a Shotstack timeline for Scooby Doo video compilation
        """
        print(f"🎬 Creating Shotstack timeline for job: {job_id}")

        # Build timeline structure
        timeline = {
            "timeline": {
                "background": "#000000",  # Black background
                "tracks": self._build_tracks(video_assets, audio_assets, transcript_data)
            },
            "output": {
                "format": "mp4",
                "resolution": "hd",
                "fps": 25,
                "quality": "medium"
            }
        }

        # Add metadata
        timeline["job_id"] = job_id
        timeline["created_at"] = time.time()
        timeline["asset_count"] = len(video_assets)

        # Save timeline JSON
        timeline_file = self.shotstack_dir / f"{job_id}_timeline.json"
        with open(timeline_file, "w") as f:
            json.dump(timeline, f, indent=2)

        print(f"✅ Created timeline: {timeline_file}")
        print(f"📊 Timeline contains {len(timeline['timeline']['tracks'])} tracks")

        return {
            "job_id": job_id,
            "timeline_file": str(timeline_file),
            "timeline_data": timeline,
            "track_count": len(timeline["timeline"]["tracks"]),
            "estimated_duration": self._estimate_duration(timeline)
        }

    def _build_tracks(self, video_assets: List[Dict[str, Any]],
                     audio_assets: List[Dict[str, Any]],
                     transcript_data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Build Shotstack tracks from video and audio assets
        """
        tracks = []

        # Video track
        if video_assets:
            video_clips = []
            current_time = 0

            for i, video in enumerate(video_assets):
                # Each video clip (assuming shorts are ~15-60 seconds)
                clip_duration = min(15, self._get_video_duration(video))  # Cap at 15 seconds

                clip = {
                    "asset": {
                        "type": "video",
                        "src": self._get_asset_url(video, "video"),
                        "volume": 0.3  # Lower volume since we'll add audio track
                    },
                    "start": current_time,
                    "length": clip_duration,
                    "fit": "cover",
                    "scale": 0.8,  # Slightly scaled for effect
                    "position": "center"
                }

                # Add text overlay with video title
                if "title" in video:
                    clip["text"] = [{
                        "text": video["title"][:50] + "..." if len(video["title"]) > 50 else video["title"],
                        "style": "minimal",
                        "color": "#ffffff",
                        "size": "medium",
                        "background": "rgba(0,0,0,0.7)",
                        "position": "bottom",
                        "offset": {"x": 0, "y": 0.1}
                    }]

                video_clips.append(clip)
                current_time += clip_duration

            tracks.append({
                "clips": video_clips
            })

        # Audio track (Scooby Doo audio)
        if audio_assets:
            audio_clips = []
            current_time = 0

            for audio in audio_assets:
                # Use full audio duration or match video duration
                audio_duration = self._get_audio_duration(audio)

                clip = {
                    "asset": {
                        "type": "audio",
                        "src": self._get_asset_url(audio, "audio"),
                        "volume": 1.0
                    },
                    "start": current_time,
                    "length": audio_duration
                }

                audio_clips.append(clip)
                current_time += audio_duration

            tracks.append({
                "clips": audio_clips
            })

        # Music track (background music)
        # Note: Music assets would be added here when available

        # Text track for transcript-based subtitles
        if transcript_data and transcript_data.get("word_timestamps"):
            subtitle_clips = self._create_subtitle_clips(transcript_data["word_timestamps"])
            if subtitle_clips:
                tracks.append({
                    "clips": subtitle_clips
                })

        return tracks

    def _create_subtitle_clips(self, word_timestamps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create subtitle clips from transcript word timestamps"""
        subtitle_clips = []

        # Group words into subtitle segments (3-5 words per subtitle)
        words_per_subtitle = 4
        current_segment = []
        segment_start = 0
        segment_end = 0

        for i, word_data in enumerate(word_timestamps):
            current_segment.append(word_data["word"])
            if segment_start == 0:
                segment_start = word_data["start_time"]
            segment_end = word_data["end_time"]

            # Create subtitle when we have enough words or reach the end
            if (i + 1) % words_per_subtitle == 0 or i == len(word_timestamps) - 1:
                subtitle_text = " ".join(current_segment)

                clip = {
                    "text": [{
                        "text": subtitle_text,
                        "style": "subtitle",
                        "color": "#ffffff",
                        "size": "medium",
                        "background": "rgba(0,0,0,0.8)",
                        "position": "bottom",
                        "offset": {"x": 0, "y": 0.05}
                    }],
                    "start": segment_start,
                    "length": segment_end - segment_start
                }

                subtitle_clips.append(clip)

                # Reset for next segment
                current_segment = []
                segment_start = 0

        return subtitle_clips

    def _get_asset_url(self, asset: Dict[str, Any], asset_type: str) -> str:
        """Get the appropriate URL for an asset"""
        # In a real implementation, this would be the Google Drive share link
        # For now, return a placeholder or the local path
        if "web_view_link" in asset:
            return asset["web_view_link"]
        elif "local_path" in asset:
            return asset["local_path"]
        else:
            return f"https://drive.google.com/file/d/{asset.get('file_id', 'unknown')}/view"

    def _get_video_duration(self, video: Dict[str, Any]) -> float:
        """Get video duration in seconds"""
        # Try to get from various sources
        if "duration_seconds" in video:
            return video["duration_seconds"]
        elif "duration" in video:
            # Parse ISO 8601 duration
            duration_str = video["duration"]
            import re
            match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
            if match:
                hours = int(match.group(1) or 0)
                minutes = int(match.group(2) or 0)
                seconds = int(match.group(3) or 0)
                return hours * 3600 + minutes * 60 + seconds
        return 15.0  # Default 15 seconds for shorts

    def _get_audio_duration(self, audio: Dict[str, Any]) -> float:
        """Get audio duration in seconds"""
        if "duration_seconds" in audio:
            return audio["duration_seconds"]
        return 15.0  # Default duration

    def _estimate_duration(self, timeline: Dict[str, Any]) -> float:
        """Estimate total timeline duration"""
        max_duration = 0

        for track in timeline["timeline"]["tracks"]:
            for clip in track.get("clips", []):
                clip_end = clip["start"] + clip["length"]
                max_duration = max(max_duration, clip_end)

        return max_duration

    def render_timeline(self, timeline_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit timeline for rendering (would call Shotstack API via MCP)
        For now, simulate the render process
        """
        job_id = timeline_data["job_id"]
        print(f"🎬 Submitting timeline for rendering: {job_id}")

        # In a real implementation, this would call:
        # mcp_Pipedream_MCP_shotstack-start-render with the timeline

        # Simulate render process
        render_id = f"render_{job_id}_{int(time.time())}"

        render_result = {
            "render_id": render_id,
            "job_id": job_id,
            "status": "queued",
            "estimated_duration": timeline_data["estimated_duration"],
            "submitted_at": time.time(),
            "mock_render": True
        }

        # Save render result
        render_file = self.shotstack_dir / f"{job_id}_render.json"
        with open(render_file, "w") as f:
            json.dump(render_result, f, indent=2)

        print(f"✅ Render submitted: {render_id}")
        return render_result

    def get_render_status(self, render_id: str) -> Dict[str, Any]:
        """Check render status (would call Shotstack API)"""
        # In real implementation, would call Shotstack status API
        return {
            "render_id": render_id,
            "status": "completed",  # Mock status
            "progress": 100,
            "output_url": f"https://shotstack-api-v1-output.s3.amazonaws.com/{render_id}.mp4"
        }


def test_shotstack_client():
    """Test the Shotstack client"""
    client = ShotstackClient()

    # Mock video assets
    mock_videos = [
        {
            "video_id": "19peKG-nkcs",
            "title": "Zarkos Kidnaps Daphne",
            "duration": "PT6S",
            "web_view_link": "https://drive.google.com/file/d/mock1/view"
        },
        {
            "video_id": "ThfK2pZA0z4",
            "title": "Daphne I'm not talking to you guys",
            "duration": "PT8S",
            "web_view_link": "https://drive.google.com/file/d/mock2/view"
        }
    ]

    # Mock audio assets
    mock_audios = [
        {
            "video_id": "19peKG-nkcs",
            "web_view_link": "https://drive.google.com/file/d/audio1/view",
            "duration_seconds": 6.0
        }
    ]

    # Mock transcript
    mock_transcript = {
        "word_timestamps": [
            {"word": "Zarkos", "start_time": 0.0, "end_time": 0.6},
            {"word": "kidnaps", "start_time": 0.65, "end_time": 1.35},
            {"word": "Daphne", "start_time": 1.4, "end_time": 2.0},
        ]
    }

    # Create timeline
    timeline_result = client.create_scooby_timeline(
        "test_job_001",
        mock_videos,
        mock_audios,
        mock_transcript
    )

    print(f"📊 Timeline creation result: {json.dumps(timeline_result, indent=2)}")

    # Test render submission
    render_result = client.render_timeline(timeline_result)
    print(f"🎬 Render result: {json.dumps(render_result, indent=2)}")


if __name__ == "__main__":
    test_shotstack_client()
