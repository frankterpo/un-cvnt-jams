# AWS SSM Templates (copy/paste)

## Set defaults (run once per shell)
```bash
REGION="us-east-1"
INSTANCE_ID="i-0aff9502a7ecee0e3"
APP="/home/ec2-user/un-cvnt-jams"
Template: send command, capture COMMAND_ID
bash
Copy code
COMMAND_ID="$(aws ssm send-command \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --comment "<COMMENT>" \
  --max-concurrency "1" \
  --max-errors "0" \
  --parameters 'commands=["bash -lc \"set -euo pipefail; cd '"$APP"'; <COMMANDS>\""]' \
  --query "Command.CommandId" \
  --output text)"
echo "COMMAND_ID=$COMMAND_ID"
Template: fetch result (short)
bash
Copy code
aws ssm get-command-invocation \
  --region "$REGION" \
  --instance-id "$INSTANCE_ID" \
  --command-id "$COMMAND_ID" \
  --query '{Status:Status,RC:ResponseCode,Stdout:StandardOutputContent,Stderr:StandardErrorContent}' \
  --output json
Example: Instagram single upload (reel)
bash
Copy code
COMMAND_ID="$(aws ssm send-command \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --comment "ucj instagram upload: test_tiktok.mp4 (reel)" \
  --max-concurrency "1" \
  --max-errors "0" \
  --parameters 'commands=["bash -lc \"set -euo pipefail; cd '"$APP"'; df -h /; PYTHONPATH=src python scripts/test_instagram_upload.py --video '"$APP"'/sample_videos/test_tiktok.mp4 --caption UCJ_IG_test --profile-dir '"$APP"'/chrome-profiles/instagram-main --post-type reel\""]' \
  --query "Command.CommandId" \
  --output text)"
aws ssm get-command-invocation \
  --region "$REGION" \
  --instance-id "$INSTANCE_ID" \
  --command-id "$COMMAND_ID" \
  --query '{Status:Status,RC:ResponseCode,Stdout:StandardOutputContent,Stderr:StandardErrorContent}' \
  --output json
Notes
Keep everything inside bash -lc "..." so it runs under bash, not sh.

Avoid parentheses ( ) in SSM commands unless heavily escaped (some earlier failures were due to parsing/quoting).
