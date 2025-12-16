#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/ec2-user/un-cvnt-jams"
if [ -d "$APP_DIR" ]; then
  cd "$APP_DIR"
else
  cd "$(cd "$(dirname "$0")/.." && pwd)"
fi

VIDEO=""
TITLE=""
PROFILE_DIR=""
HEADLESS="false"

while [ $# -gt 0 ]; do
  case "$1" in
    --video)
      VIDEO="${2:-}"
      shift 2
      ;;
    --title)
      TITLE="${2:-}"
      shift 2
      ;;
    --profile-dir)
      PROFILE_DIR="${2:-}"
      shift 2
      ;;
    --headless)
      HEADLESS="true"
      shift 1
      ;;
    *)
      echo "Unknown arg: $1" 1>&2
      exit 2
      ;;
  esac
done

if [ -z "$VIDEO" ] || [ -z "$TITLE" ] || [ -z "$PROFILE_DIR" ]; then
  echo "Usage: $0 --video /abs/video.mp4 --title UCJ_YT_test --profile-dir /abs/profile [--headless]" 1>&2
  exit 2
fi

. .venv/bin/activate
PYTHONPATH=src python -c "import dotenv" >/dev/null

ARGS=(--video "$VIDEO" --title "$TITLE" --profile-dir "$PROFILE_DIR")
if [ "$HEADLESS" = "true" ]; then
  ARGS+=(--headless)
fi

PYTHONPATH=src python scripts/test_youtube_upload.py "${ARGS[@]}"

