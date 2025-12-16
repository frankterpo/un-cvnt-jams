# SSM visibility options for long-running Instagram runs

## Option 1 (best for debugging): interactive SSM shell + tail logs
1) Start session:
```bash
aws ssm start-session --region us-east-1 --target i-0aff9502a7ecee0e3
```

2) Run:
```bash
sudo -u ec2-user -H bash -lc "/home/ec2-user/un-cvnt-jams/scripts/run_instagram_upload_run.sh --video ... --caption ... --profile-dir ... --post-type reel --interactive-login"
```

3) In a second session:
```bash
tail -f /tmp/ig_runs/<RUN_ID>/run.log
```

---

## Option 2: `send-command` + CloudWatch logs (hands-off)
This avoids “only InProgress” by streaming output into CloudWatch.

### 2.1 Create a log group (one-time)
```bash
aws logs create-log-group --log-group-name "/ssm/un-cvnt-jams" --region us-east-1 || true
```

### 2.2 Send command
```bash
REGION=us-east-1
INSTANCE_ID=i-0aff9502a7ecee0e3

CMD_ID="$(aws ssm send-command   --region "$REGION"   --instance-ids "$INSTANCE_ID"   --document-name "AWS-RunShellScript"   --comment "ig run (with cloudwatch output)"   --cloud-watch-output-config CloudWatchOutputEnabled=true,CloudWatchLogGroupName=/ssm/un-cvnt-jams   --parameters commands='[
    "set -euo pipefail",
    "APP=/home/ec2-user/un-cvnt-jams",
    "PROFILE_DIR=$APP/chrome-profiles/instagram-main",
    "VIDEO=$APP/sample_videos/test_tiktok.mp4",
    "sudo -u ec2-user -H bash -lc \"$APP/scripts/run_instagram_upload_run.sh --video $VIDEO --caption UCJ_IG_test --profile-dir $PROFILE_DIR --post-type reel --interactive-login\""
  ]'   --query "Command.CommandId"   --output text)"

echo "CMD_ID=$CMD_ID"
```

### 2.3 Check status + fetch output
```bash
aws ssm get-command-invocation   --region us-east-1   --instance-id i-0aff9502a7ecee0e3   --command-id "$CMD_ID"   --query '{Status:Status,RC:ResponseCode,Stdout:StandardOutputContent,Stderr:StandardErrorContent}'   --output json
```

### 2.4 Tail CloudWatch
```bash
aws logs tail "/ssm/un-cvnt-jams" --since 10m --follow --region us-east-1
```

Notes:
- Avoid parentheses in unquoted `echo` lines inside `send-command`; use quotes.
- Keep commands as simple strings; complex quoting belongs in instance scripts.
