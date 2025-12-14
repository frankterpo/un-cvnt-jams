# Objective
Run exactly 1 upload per platform on EC2: Instagram -> YouTube -> TikTok

# EC2 constants
REGION=us-east-1
INSTANCE_ID=i-0aff9502a7ecee0e3
APP=/home/ec2-user/un-cvnt-jams

# Known good paths on EC2
IG_PROFILE=/home/ec2-user/un-cvnt-jams/chrome-profiles/instagram-main
YT_PROFILE=/home/ec2-user/un-cvnt-jams/chrome-profiles/youtube-main

# Candidate videos (local repo paths)
./sample_videos/test_youtube.mp4
./sample_videos/test_tiktok.mp4
./pipeline_output/videos/de30ed81_2_de30ed81_2_video_placeholder.mp4

# Known issues so far
- IG script requires --profile-dir; fixed by passing EC2 profile dir
- Selenium failed due to missing Chrome/driver + "No space left on device" earlier
- Some SSM commands failed due to shell parsing; keep SSM commands extremely simple

# Latest outputs
(append new SSM outputs below each run)

## 2025-12-14 - step name here
PASTE THE get-command-invocation JSON HERE

## Accounts (NO SECRETS)
- Account labels live in: .codex/accounts_index.json
- Instagram auth MUST use chrome profile dirs (already logged-in), not passwords.
  - Profiles live under: /home/ec2-user/un-cvnt-jams/chrome-profiles/<label-or-alias>
- TikTok auth MUST use cookies file, not passwords.
  - Cookies path comes from env var: TIKTOK_COOKIES_PATH

Rules:
- Never print credentials, cookies, session tokens, or full profile contents in stdout.
- If login is required, stop and ask for a manual-login step (no captcha/2FA bypass attempts).
