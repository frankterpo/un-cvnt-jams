import os
from pathlib import Path

# API Keys and Credentials
GOOGLE_STUDIO_API_KEY = "AIzaSyBLkOh_EZV9OrYB-COhmuW2PgnKVnxzwZU"  # For Speech-to-Text
YOUTUBE_API_KEY = "AIzaSyAi5hSVgYv9aZEnsroMP1qXYDEa_Lbezm4"  # Working YouTube API key
SERVICE_ACCOUNT_FILE = "blissful-fiber-473419-e6-abf91b637595.json"

# YouTube Search Configuration
YOUTUBE_SEARCH_QUERY = "daphne scooby doo quotes"  # Exact search query required
YOUTUBE_MAX_RESULTS = 50  # Get more to filter down to valid shorts

# Scooby Doo Channel IDs for targeted Shorts search
# High-quality channels that produce Daphne Scooby Doo content
SCOOBY_CHANNELS = [
    "UC4PrHyjwN1B8V5OjqZ8M8pQ",  # @BoomerangUK
    "UCvBzO9RK7qRTrUJHt5dJfWw",  # @PixaWaveStudio (estimated)
    "UCY8nTQnC2J2wxpPj3qT7JLQ",  # @hbomaxfamily (estimated)
    "UCvBzO9RK7qRTrUJHt5dJfWw",  # @GenerationWB (estimated)
    # Note: Need to verify actual channel IDs
]

# YouTube Shorts Playlist Prefixes
YOUTUBE_SHORTS_PREFIX = "UUSH"  # UC + channel_id -> UUSH + channel_id for shorts playlist
# YOUTUBE_API_KEY is now defined above

# Google Drive Folder IDs
GDRIVE_FOLDERS = {
    "audio": "1DsZvcbJtEObhP8NkLrkrHc5ICSjuRWtf",      # .mp3 of youtube video
    "video": "1sUGWyD_bnhfPBAAo24jlQ-lO5mBm-faN",      # .mp4 of youtube video
    "transcription": "1p26m9wBlAWBJidQMVbdVhJqvu3BnmEkt", # transcription files
    "music": "1ofweNntzmckkjvWW-BQ_HKTvOxN0AEU-"      # .wav and .mp3 of music
}

# Local Directories
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "pipeline_output"
DOWNLOADS_DIR = OUTPUT_DIR / "downloads"
TRANSCRIPTS_DIR = OUTPUT_DIR / "transcripts"
TEMP_DIR = OUTPUT_DIR / "temp"

# yt-dlp Configuration
YTDLP_CONFIG = {
    "format": "best[height<=720]",  # Limit quality for shorts
    "outtmpl": str(DOWNLOADS_DIR / "%(id)s.%(ext)s"),
    "noplaylist": True,
    "nooverwrites": True,
    "quiet": False,
    "extract_flat": False,
}

# Google Speech-to-Text Configuration
SPEECH_CONFIG = {
    "encoding": "LINEAR16",
    "sample_rate_hertz": 16000,
    "language_code": "en-US",
    "model": "chirp",  # Using Chirp model as requested
    "use_enhanced": True,
}

# Shotstack Configuration (via MCP)
SHOTSTACK_CONFIG = {
    "timeline": {
        "background": "#000000",
        "tracks": []
    }
}

# Create directories
for dir_path in [OUTPUT_DIR, DOWNLOADS_DIR, TRANSCRIPTS_DIR, TEMP_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)
