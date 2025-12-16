#!/usr/bin/env bash
set -euo pipefail

REGION="${REGION:-us-east-1}"
INSTANCE_ID="${INSTANCE_ID:-}"
VIDEO="${VIDEO:-}"
CAPTION="${CAPTION:-}"
PROFILE_DIR="${PROFILE_DIR:-}"
POST_TYPE="${POST_TYPE:-reel}"
CLOUDWATCH_LOG_GROUP="${CLOUDWATCH_LOG_GROUP:-/ssm/un-cvnt-jams}"

if [ -z "$INSTANCE_ID" ] || [ -z "$VIDEO" ] || [ -z "$CAPTION" ] || [ -z "$PROFILE_DIR" ]; then
  echo "Usage:" 1>&2
  echo "  REGION=us-east-1 INSTANCE_ID=i-... VIDEO=/home/ec2-user/un-cvnt-jams/... CAPTION=UCJ_IG_test PROFILE_DIR=/home/ec2-user/un-cvnt-jams/chrome-profiles/instagram-main $0" 1>&2
  exit 2
fi

case "$CAPTION" in
  *" "*)
    echo "Error: CAPTION contains spaces; use a caption without spaces for safe SSM quoting." 1>&2
    exit 2
    ;;
esac

aws logs create-log-group --log-group-name "$CLOUDWATCH_LOG_GROUP" --region "$REGION" >/dev/null 2>&1 || true

CMD_ID="$(aws ssm send-command \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --comment "ucj ig run (cloudwatch output)" \
  --cloud-watch-output-config CloudWatchOutputEnabled=true,CloudWatchLogGroupName="$CLOUDWATCH_LOG_GROUP" \
  --parameters 'commands=["set -euo pipefail","cd /home/ec2-user/un-cvnt-jams",". .venv/bin/activate","python -c \"import dotenv\"","df -h /","command -v google-chrome","command -v chromedriver","sudo -u ec2-user -H ./scripts/run_instagram_upload_run.sh --video '"$VIDEO"' --caption '"$CAPTION"' --profile-dir '"$PROFILE_DIR"' --post-type '"$POST_TYPE"' --interactive-login"]' \
  --query "Command.CommandId" \
  --output text)"

echo "CMD_ID=$CMD_ID"
echo "aws ssm get-command-invocation --region $REGION --instance-id $INSTANCE_ID --command-id $CMD_ID --plugin-name aws:runShellScript --output json"
echo "aws logs tail \"$CLOUDWATCH_LOG_GROUP\" --since 10m --follow --region $REGION"

