# Social Media Automation Agent

A robust, production-ready system for automated social media posting across TikTok, YouTube, and Instagram. **All platforms are fully functional with smart automation that adapts to UI changes.**

## ✅ Status

- **TikTok**: ✅ Working (cookie-based, ~45s uploads)
- **YouTube**: ✅ Working (profile-based, ~55s uploads)
- **Instagram**: ✅ Working (smart modals, ~55s uploads)
- **AI Captions**: ✅ Ollama integration ready
- **GDrive Integration**: ✅ Automated sourcing ready

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up authentication (choose platforms you want)
python scripts/tiktok_login_cookies.py --cookies-path cookies/tiktok_cookies.txt
python scripts/youtube_login_profile.py --profile-dir chrome-profiles/youtube-main
python scripts/instagram_login_profile.py --profile-dir chrome-profiles/instagram-main

# 3. Configure environment (.env file)
echo "TIKTOK_COOKIES_PATH=cookies/tiktok_cookies.txt" > .env
echo "YOUTUBE_PROFILE_DIR=chrome-profiles/youtube-main" >> .env
echo "INSTAGRAM_PROFILE_DIR=chrome-profiles/instagram-main" >> .env

# 4. Test individual platforms
PYTHONPATH=src python scripts/test_tiktok_upload.py --video sample_videos/test_tiktok.mp4 --caption "Test"
PYTHONPATH=src python scripts/test_youtube_upload.py --video sample_videos/test_youtube.mp4 --title "Test" --description "Test"
PYTHONPATH=src python scripts/test_instagram_upload.py --video sample_videos/test_tiktok.mp4 --caption "Test"

# 5. Run full automation (with GDrive + AI)
PYTHONPATH=src python scripts/ollama_agent.py
```

## 🚀 Features

- **Multi-platform support**: TikTok, YouTube, and Instagram
- **Smart automation**: Dynamic element detection, no brittle selectors
- **Idempotent uploads**: Prevents duplicate posts
- **AI-powered captions**: Ollama integration for intelligent content generation
- **Google Drive integration**: Automated video sourcing
- **Headless & headful modes**: Flexible deployment options
- **Optimized performance**: ~45-55 seconds per upload

## 📁 Project Structure

```
├── src/agent/                    # Core agent logic
│   ├── config.py                # Configuration management
│   ├── workflow.py              # Main upload orchestration
│   ├── state.py                 # Upload state tracking
│   ├── captions.py              # Caption generation
│   ├── captions_ollama.py       # AI caption generation
│   ├── source_gdrive.py         # Google Drive integration
│   ├── __main__.py              # CLI entry point
│   └── __init__.py              # Package init
├── src/tools/                   # Platform-specific tools
│   ├── tiktok_*.py              # TikTok upload client (auth, browser, client, selectors)
│   ├── youtube_*.py             # YouTube upload client (browser, client, selectors, metadata)
│   ├── instagram_*.py           # Instagram upload client (browser, client, selectors)
│   └── ai_locator.py            # AI element locator (optional)
├── scripts/                     # Testing & utility scripts
│   ├── test_*.py                # Individual platform tests
│   ├── *_login_*.py             # Profile/cookie setup
│   ├── run_from_gdrive.py       # Direct GDrive workflow
│   ├── ollama_agent.py          # Full AI pipeline
│   └── sanity_check.py          # Configuration validation
├── accounts.json                # Account credentials (Instagram/TikTok)
├── cookies/tiktok_cookies.txt   # TikTok authentication cookies
├── blissful-fiber-*.json        # Google Drive service account key
├── sample_videos/               # Test video files
├── chrome-profiles/             # Browser profiles (auto-created)
├── README.md                    # This documentation
└── requirements.txt             # Python dependencies
```

## ⚙️ Setup

### 1. Environment Variables

Create a `.env` file in the project root:

```bash
# TikTok Configuration
TIKTOK_COOKIES_PATH=/path/to/tiktok_cookies.txt
TIKTOK_HEADLESS=false

# YouTube Configuration
YOUTUBE_PROFILE_DIR=/path/to/chrome-profiles/youtube-main
YOUTUBE_HEADLESS=false

# Instagram Configuration
INSTAGRAM_PROFILE_DIR=/path/to/chrome-profiles/instagram-main
INSTAGRAM_HEADLESS=false

# Google Drive (optional)
GDRIVE_SA_JSON=/path/to/service-account.json
GDRIVE_FOLDER_ID=your_folder_id

# Ollama (optional)
OLLAMA_URL=http://localhost:11434/api/chat
OLLAMA_MODEL=llama3.1
```

### 2. Authentication Setup

#### TikTok
```bash
# Capture cookies
python scripts/tiktok_login_cookies.py --cookies-path cookies/tiktok_cookies.txt
```

#### YouTube
```bash
# Create logged-in profile
python scripts/youtube_login_profile.py --profile-dir chrome-profiles/youtube-main
```

#### Instagram
```bash
# Create logged-in profile
python scripts/instagram_login_profile.py --profile-dir chrome-profiles/instagram-main
```

### 3. Dependencies

```bash
pip install -r requirements.txt
```

## 🎯 Usage

### Individual Platform Testing

```bash
# Test TikTok
PYTHONPATH=src python scripts/test_tiktok_upload.py --video sample_videos/test_tiktok.mp4 --caption "Test upload"

# Test YouTube
PYTHONPATH=src python scripts/test_youtube_upload.py --video sample_videos/test_youtube.mp4 --title "Test Video" --description "Test description"

# Test Instagram
PYTHONPATH=src python scripts/test_instagram_upload.py --video sample_videos/test_tiktok.mp4 --caption "Test post"
```

### Full Pipeline (GDrive + AI)

```bash
# Run complete automation pipeline
PYTHONPATH=src python scripts/ollama_agent.py
```

### Direct GDrive Workflow

```bash
# Process videos from Google Drive
PYTHONPATH=src python scripts/run_from_gdrive.py
```

## 🔧 Configuration Details

### Account Credentials (`accounts.json`)

```json
{
  "instagram": {
    "accounts": [
      {
        "username": "your_username",
        "password": "your_password"
      }
    ]
  },
  "tiktok": {
    "accounts": [
      {
        "username": "your_username",
        "password": "your_password"
      }
    ]
  }
}
```

### Upload State Tracking

The system maintains `pipeline_output/upload_state.json` (auto-created) to track successful uploads and prevent duplicates:

```json
{
  "file_id_platform": "timestamp",
  "drive_file_123_tiktok": "2025-12-12T00:00:00",
  "drive_file_123_youtube": "2025-12-12T00:01:00",
  "drive_file_123_instagram": "2025-12-12T00:02:00"
}
```

This ensures videos are never uploaded twice to the same platform.

## 🚦 Platform-Specific Notes

### TikTok
- Uses Netscape-format cookies for authentication
- Requires manual cookie capture via browser
- Headless mode supported
- **Performance**: ~45 seconds per upload
- **Smart features**: Automatic tutorial overlay dismissal

### YouTube
- Uses Chrome profile for authentication
- Supports scheduled publishing
- Multi-step upload wizard (Details → Checks → Visibility)
- **Performance**: ~55 seconds per upload
- **Smart features**: Automatic Next button progression, Done button retry

### Instagram
- Uses Chrome profile for authentication
- Handles cookie banners and login modals automatically
- **Smart modal navigation with dynamic button detection**
- **Performance**: ~55 seconds per upload (optimized)
- **Smart features**: Role-based button finding, JavaScript fallbacks, modal dismissal

## 🔍 Debugging

### Debug Files
When uploads fail, debug HTML dumps are created:
- `debug_tiktok_*.html`
- `debug_youtube_*.html`
- `debug_instagram_*.html`

### Common Issues

1. **"Session not created"**: Delete and recreate Chrome profiles
2. **"Element not found"**: Check if platform UI changed, debug dumps will help
3. **"Already uploaded"**: Check `upload_state.json` for duplicate prevention

### Performance Tuning

- Set `*_HEADLESS=true` for server deployment
- Adjust timeouts in client code for slower networks
- Use `sanity_check.py` to validate configuration

## 🧠 Smart Technology

Unlike traditional automation scripts with brittle selectors, this system uses **intelligent element detection**:

### Smart Element Detection
- **Dynamic XPath selectors** with multiple fallback strategies
- **Role-based targeting** (`role="button"`) for reliable element finding
- **Text content matching** for buttons without stable IDs
- **JavaScript injection** for complex UI interactions
- **AI-powered locator** (optional) for advanced cases

### Platform-Specific Intelligence
- **Instagram**: Automatic modal navigation, cookie banner dismissal, login modal handling
- **YouTube**: Multi-step wizard progression, scheduled publishing support
- **TikTok**: Tutorial overlay dismissal, upload progress monitoring

### Idempotency & Reliability
- **File-based state tracking** prevents duplicate uploads
- **Platform-specific records** ensure cross-platform uniqueness
- **Automatic retry logic** for transient failures
- **Debug dumps** for troubleshooting UI changes

### Error Handling
- **Comprehensive exception catching** with platform-specific error types
- **Graceful degradation** with fallback strategies
- **Timeout management** for different network conditions
- **Logging standardization** across all platforms

## 🤖 AI Integration

### Ollama Caption Generation
The system can generate platform-specific captions using local AI:

```python
from agent.captions_ollama import generate_captions_with_ollama

captions = generate_captions_with_ollama(
    title="My Video Title",
    context="Additional context"
)
```

### Optional AI Element Locator
For advanced cases, an AI-powered element locator is available:

```python
from tools.ai_locator import suggest_selector

selector = suggest_selector("youtube_upload_button", html_content)
```

## 🚀 Production Deployment

1. Set all `*_HEADLESS=true` in `.env`
2. Use service accounts for Google Drive
3. Run on a server with stable internet
4. Monitor logs for upload status
5. Set up cron jobs for automated posting

## 📝 Development

### Adding New Platforms
1. Create platform client in `src/tools/`
2. Add selectors file for DOM elements
3. Implement browser setup and upload logic
4. Add to `workflow.py` dispatch
5. Create test script in `scripts/`

### Extending AI Features
- Modify `captions_ollama.py` for custom prompts
- Enhance `ai_locator.py` for better element detection
- Add new LLM integrations

## 📄 License

This project is for educational and personal use. Please respect platform terms of service and rate limits.