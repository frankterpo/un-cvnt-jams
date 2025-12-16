#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/ec2-user/un-cvnt-jams"
if [ -d "$APP_DIR" ]; then
  cd "$APP_DIR"
else
  cd "$(cd "$(dirname "$0")/.." && pwd)"
fi

VIDEO=""
CAPTION=""
HEADLESS="false"

while [ $# -gt 0 ]; do
  case "$1" in
    --video)
      VIDEO="${2:-}"
      shift 2
      ;;
    --caption)
      CAPTION="${2:-}"
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

if [ -z "$VIDEO" ] || [ -z "$CAPTION" ]; then
  echo "Usage: $0 --video /abs/video.mp4 --caption UCJ_TT_test [--headless]" 1>&2
  exit 2
fi

. .venv/bin/activate
PYTHONPATH=src python -c "import dotenv" >/dev/null

if [ -z "${TIKTOK_COOKIES_PATH:-}" ]; then
  echo "Error: TIKTOK_COOKIES_PATH is not set" 1>&2
  exit 2
fi
if [ ! -f "${TIKTOK_COOKIES_PATH}" ]; then
  echo "Error: TIKTOK_COOKIES_PATH does not point to a file" 1>&2
  exit 2
fi

ARGS=(--video "$VIDEO" --caption "$CAPTION")
if [ "$HEADLESS" = "true" ]; then
  ARGS+=(--headless)
fi

PYTHONPATH=src python scripts/test_tiktok_upload.py "${ARGS[@]}"

