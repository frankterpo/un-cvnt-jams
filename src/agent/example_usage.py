"""Example usage of the social media upload workflow."""

from pathlib import Path

from agent.config import load_settings
from agent.workflow import run_cycle_single


def example_basic_usage() -> None:
    """Example of basic usage with all platforms."""
    settings = load_settings()

    video_path = Path("path/to/video.mp4")

    captions = {
        "tiktok": "Check out this amazing video! #viral #fyp",
        "youtube": {
            "title": "Amazing Video Title",
            "description": "This is a great video description.",
            "tags": ["amazing", "video", "content"],
        },
        "instagram": "Check out this amazing video! #instagood #viral",
    }

    results = run_cycle_single(
        settings,
        video_path,
        captions,
        target_platforms=["tiktok", "youtube", "instagram"],
        drive_file_id="example-video-1",
    )

    for platform, result in results.items():
        if result["status"] == "success":
            print(f"✅ {platform}: Upload successful")
            if "video_id" in result:
                print(f"   Video ID: {result['video_id']}")
        elif result["status"] == "skipped":
            print(f"⏭️ {platform}: Skipped - {result.get('reason', 'unknown')}")
        else:
            print(f"❌ {platform}: Upload failed - {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    example_basic_usage()

