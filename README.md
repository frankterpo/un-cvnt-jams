# Scooby Doo Video Pipeline 🎭

A complete automated pipeline that discovers Scooby Doo YouTube shorts, downloads media, transcribes audio, uploads to Google Drive, and creates Shotstack video timelines.

## 🚀 Pipeline Overview

1. **YouTube Search** → Find Daphne Scooby Doo quote YouTube shorts only
2. **Media Download** → Download MP4 video + MP3 audio using yt-dlp
3. **Speech Transcription** → Transcribe audio using Google Speech-to-Text (Chirp model)
4. **Google Drive Upload** → Upload assets to organized folders
5. **Shotstack Timeline** → Create video compilation timeline with subtitles

## 📋 Features

- ✅ **YouTube Data API v3** integration for short discovery
- ✅ **Premium channel prioritization** - @BoomerangUK, @PixaWaveStudio, @hbomaxfamily, @GenerationWB
- ✅ **8-second maximum duration** - Ultra-short clips only
- ✅ **Channel-specific search** - Uses `channelId` parameter for targeted results
- ✅ **Strict YouTube shorts only** - URLs start with https://www.youtube.com/shorts/
- ✅ **Daphne Scooby Doo quotes search** - Exact query "daphne scooby doo quotes"
- ✅ **Creative Commons filtering** for safe content usage
- ✅ **Advanced deduplication** - zero duplicate videos across jobs
- ✅ **Content validation** - Ensures all videos contain Daphne/Scooby keywords
- ✅ **yt-dlp integration** for reliable media downloads
- ✅ **Google Speech-to-Text** with Chirp model for transcription
- ✅ **Google Drive API** for organized asset storage
- ✅ **Shotstack MCP** integration for video rendering
- ✅ **Job tracking system** with unique IDs
- ✅ **Mock mode** for testing without API keys

### 🔄 Deduplication System

The pipeline uses a sophisticated deduplication system to ensure no duplicate videos are processed:

- **Search-level deduplication**: Removes duplicates from YouTube API results using video ID and title similarity
- **Job-level deduplication**: Tracks videos processed in recent jobs (last 7 days) and skips them
- **Cross-job awareness**: Each new pipeline run automatically skips videos processed in previous runs

This ensures fresh content for each pipeline execution while maintaining efficiency.

### 🔍 Advanced Search Methodology

The pipeline uses a sophisticated multi-stage search approach to find the best Daphne Scooby Doo shorts:

1. **Channel Discovery**: Searches for YouTube channels related to Scooby Doo content
2. **Shorts Playlist Access**: Converts channel IDs to shorts playlist IDs using `UUSH + channel_suffix`
3. **Playlist Search**: Searches within each channel's shorts playlist for relevant content
4. **Fallback Search**: Supplements with traditional search for comprehensive coverage
5. **Content Validation**: Applies strict filtering for Daphne quotes and YouTube Shorts format

This approach provides higher quality, more relevant results than simple keyword searches.

### 🎯 Ultra-Strict Content Requirements

The pipeline enforces extremely strict validation for premium Daphne Scooby Doo content:

- **Search Query**: Exactly "daphne scooby doo quotes"
- **Duration Limit**: Maximum 8 seconds (ultra-short clips only)
- **Video Type**: YouTube Shorts only (`https://www.youtube.com/shorts/` URLs)
- **Premium Channels**: Prioritizes @BoomerangUK, @PixaWaveStudio, @hbomaxfamily, @GenerationWB
- **Content Validation**: Must contain Daphne/Scooby related keywords
- **Deduplication**: Zero duplicate video IDs or similar titles
- **Creative Commons**: Only licensed content for safe reuse

## 🛠️ Installation

```bash
# Clone and setup
cd /path/to/project
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## ⚙️ Configuration

### API Keys Setup

1. **Google Cloud Console**: https://console.cloud.google.com/
2. **YouTube Data API v3**: Enable and get API key
3. **Speech-to-Text API**: Enable for transcription
4. **Google Drive API**: Enable for uploads

### Environment Variables

```bash
# For production use
export YOUTUBE_API_KEY="your_youtube_api_key"
export GOOGLE_STUDIO_API_KEY="your_speech_api_key"
```

### Google Drive Folders

The pipeline uploads to these pre-shared Google Drive folders:

- **Audio**: `1DsZvcbJtEObhP8NkLrkrHc5ICSjuRWtf`
- **Video**: `1sUGWyD_bnhfPBAAo24jlQ-lO5mBm-faN`
- **Transcription**: `1p26m9wBlAWBJidQMVbdVhJqvu3BnmEkt`
- **Music**: `1ofweNntzmckkjvWW-BQ_HKTvOxN0AEU-`

## 🎯 Usage

### Run Complete Pipeline

```bash
# Run with mock services (default, processes 3 videos)
python scooby_pipeline.py

# Specify number of videos (1-50)
python scooby_pipeline.py --max-videos 10
python scooby_pipeline.py -n 5

# Run with real APIs (requires API keys)
python scooby_pipeline.py --real --max-videos 5

# Check pipeline help
python scooby_pipeline.py --help
```

### Job Management

```bash
# List all jobs
python scooby_pipeline.py --list-jobs

# Check specific job status
python scooby_pipeline.py --job-id scooby_20250928_100103_b393
```

### Individual Components

```bash
# Test YouTube search only
python youtube_search.py

# Test media downloads
python media_downloader.py

# Test transcription
python speech_transcriber.py

# Test Google Drive upload
python google_drive_uploader.py

# Test Shotstack timeline creation
python shotstack_client.py
```

## 📁 Output Structure

```
pipeline_output/
├── downloads/           # Downloaded MP4/MP3 files
├── transcripts/         # JSON transcription files
├── shotstack/          # Timeline and render files
├── jobs/               # Job tracking files
└── logs/               # Pipeline logs
```

## 🎬 Pipeline Steps

### 1. YouTube Search
- Searches for Scooby Doo shorts using hashtags:
  - `#ScoobyDoo #SarahMichelleGellar #DaphneBlake #buffythevampireslayer`
- Filters for Creative Commons licensed content
- Returns top videos by relevance

### 2. Media Download
- Downloads MP4 video (720p max, ~15-60 seconds)
- Downloads MP3 audio (128kbps)
- Uses yt-dlp for reliable downloads

### 3. Speech Transcription
- Uses Google Speech-to-Text Chirp model
- Creates word-level timestamps
- Generates subtitle-compatible output

### 4. Google Drive Upload
- Uploads videos to Video folder
- Uploads audio to Audio folder
- Uploads transcripts to Transcription folder
- Generates shareable links

### 5. Shotstack Timeline Creation
- Creates multi-track video timeline
- Adds video clips with text overlays
- Includes audio tracks
- Generates subtitle tracks from transcripts

## 🔧 Configuration Files

- `config.py` - API keys, folder IDs, settings
- `requirements.txt` - Python dependencies
- Service account JSON for Google APIs

## 🎭 Mock Mode

For testing without API keys, the pipeline includes mock implementations:

```bash
# Use mock mode (default)
python scooby_pipeline.py

# The following components have mock fallbacks:
# - Speech-to-Text → Mock transcription
# - Google Drive → Mock upload URLs
# - Shotstack → Mock render submission
```

## 📊 Job Tracking

Each pipeline run creates a unique job ID and tracks:

- Job status and progress
- Asset counts and locations
- Step-by-step execution logs
- Error handling and recovery

## 🚨 Important Notes

### API Limitations
- **YouTube API**: 10,000 units/day free quota
- **Speech-to-Text**: Pay-per-use pricing
- **Google Drive**: Service account storage limits

### Content Usage
- Only processes Creative Commons licensed content
- Always verify license terms before public use
- Include attribution for creators

### Production Setup
1. Enable required Google Cloud APIs
2. Set up service account with proper permissions
3. Configure Google Drive folder sharing
4. Set up Shotstack account and API access

## 🐛 Troubleshooting

### Common Issues

**"API key not valid"**
- Check API key is correct and YouTube Data API is enabled

**"Service account storage quota"**
- Service accounts have limited storage; use shared drives

**"Transcription failed"**
- Enable Speech-to-Text API in Google Cloud Console

**"Download failed"**
- Check yt-dlp is installed: `yt-dlp --version`

## 📈 Performance

- **YouTube Search**: ~2-5 seconds
- **Media Download**: ~10-30 seconds per video
- **Transcription**: ~5-15 seconds per audio file
- **Drive Upload**: ~5-10 seconds per file
- **Timeline Creation**: ~1-2 seconds

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Submit pull request

## 📄 License

This project processes Creative Commons licensed content only.
Ensure compliance with YouTube Terms of Service and content creator licenses.

---

**Built with ❤️ for Scooby Doo fans everywhere!** 🐕👻
