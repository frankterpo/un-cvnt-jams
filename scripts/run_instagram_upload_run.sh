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
PROFILE_DIR=""
POST_TYPE="reel"
INTERACTIVE_LOGIN="false"
INTERACTIVE_TIMEOUT_SECS=""
CDP_PORT=""

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
    --profile-dir)
      PROFILE_DIR="${2:-}"
      shift 2
      ;;
    --post-type)
      POST_TYPE="${2:-}"
      shift 2
      ;;
    --interactive-login)
      INTERACTIVE_LOGIN="true"
      shift 1
      ;;
    --interactive-timeout-secs)
      INTERACTIVE_TIMEOUT_SECS="${2:-}"
      shift 2
      ;;
    --cdp-port)
      CDP_PORT="${2:-}"
      shift 2
      ;;
    *)
      echo "Unknown arg: $1" 1>&2
      exit 2
      ;;
  esac
done

if [ -z "$VIDEO" ] || [ -z "$CAPTION" ] || [ -z "$PROFILE_DIR" ]; then
  echo "Usage: $0 --video /abs/video.mp4 --caption UCJ_IG_test --profile-dir /abs/profile --post-type reel [--interactive-login]" 1>&2
  exit 2
fi

RUN_ID="${IG_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}_${RANDOM}"
DEBUG_DIR="${IG_DEBUG_DIR:-/tmp/ig_runs/${RUN_ID}}"
mkdir -p "$DEBUG_DIR"

export IG_RUN_ID="$RUN_ID"
export IG_DEBUG_DIR="$DEBUG_DIR"
export IG_INTERACTIVE_LOGIN="$INTERACTIVE_LOGIN"
if [ -n "$INTERACTIVE_TIMEOUT_SECS" ]; then
  export IG_INTERACTIVE_TIMEOUT_SECS="$INTERACTIVE_TIMEOUT_SECS"
fi
if [ -n "$CDP_PORT" ]; then
  export IG_CDP_PORT="$CDP_PORT"
fi
if [ -z "${INSTAGRAM_HEADLESS:-}" ]; then
  export INSTAGRAM_HEADLESS=true
fi

echo "RUN_ID=$RUN_ID"
echo "DEBUG_DIR=$DEBUG_DIR"

START_EPOCH="$(date +%s)"

pkill -f chromedriver >/dev/null 2>&1 || true
pkill -f google-chrome >/dev/null 2>&1 || true
pkill -f "python scripts/test_instagram_upload.py" >/dev/null 2>&1 || true

sudo chown -R ec2-user:ec2-user "$PROFILE_DIR" >/dev/null 2>&1 || true
rm -f "$PROFILE_DIR/SingletonLock" "$PROFILE_DIR/SingletonSocket" "$PROFILE_DIR/SingletonCookie" || true
rm -f "$PROFILE_DIR/Default/SingletonLock" "$PROFILE_DIR/Default/SingletonSocket" "$PROFILE_DIR/Default/SingletonCookie" || true
rm -f "$PROFILE_DIR/Profile 1/SingletonLock" "$PROFILE_DIR/Profile 1/SingletonSocket" "$PROFILE_DIR/Profile 1/SingletonCookie" || true

. .venv/bin/activate

EXTRA_ARGS=()
if [ "$INTERACTIVE_LOGIN" = "true" ]; then
  EXTRA_ARGS+=(--interactive-login)
fi
if [ -n "$INTERACTIVE_TIMEOUT_SECS" ]; then
  EXTRA_ARGS+=(--interactive-timeout-secs "$INTERACTIVE_TIMEOUT_SECS")
fi
if [ -n "$CDP_PORT" ]; then
  EXTRA_ARGS+=(--cdp-port "$CDP_PORT")
fi

set +e
PYTHONPATH=src python scripts/test_instagram_upload.py \
  --video "$VIDEO" \
  --caption "$CAPTION" \
  --profile-dir "$PROFILE_DIR" \
  --post-type "$POST_TYPE" \
  --run-id "$RUN_ID" \
  --debug-dir "$DEBUG_DIR" \
  "${EXTRA_ARGS[@]}" \
  2>&1 | tee "$DEBUG_DIR/run.log"
RC="${PIPESTATUS[0]}"
set -e

END_EPOCH="$(date +%s)"
RUNTIME_SECS="$((END_EPOCH - START_EPOCH))"

python - "$DEBUG_DIR" "$RUN_ID" "$RC" "$RUNTIME_SECS" <<'PY'
import json
import sys
from pathlib import Path

debug_dir = Path(sys.argv[1])
run_id = sys.argv[2]
rc = int(sys.argv[3])
runtime_secs = int(sys.argv[4])

last_step = ""
steps_path = debug_dir / "steps.jsonl"
try:
    if steps_path.exists():
        lines = steps_path.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
        if lines:
            last_step = json.loads(lines[-1]).get("step", "") or ""
except Exception:
    last_step = ""

summary = {
    "run_id": run_id,
    "debug_dir": str(debug_dir),
    "rc": rc,
    "runtime_secs": runtime_secs,
    "last_step": last_step,
}
(debug_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
PY

if [ "${IG_ZIP_ARTIFACTS:-false}" = "true" ]; then
  if command -v zip >/dev/null 2>&1; then
    zip -qr "/tmp/ig_runs/${RUN_ID}.zip" "$DEBUG_DIR" >/dev/null 2>&1 || true
  fi
fi

exit "$RC"
