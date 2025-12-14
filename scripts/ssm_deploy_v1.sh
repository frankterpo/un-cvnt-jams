#!/usr/bin/env bash
set -euo pipefail

# === V1 SSM Deploy Script ===
# Deterministic: fresh clone, build, restart, test
# Polls by exact CommandId. Never uses list-command-invocations.

REGION="us-east-1"
INSTANCE_ID="i-0aff9502a7ecee0e3"
REPO_URL="https://github.com/frankterpo/un-cvnt-jams.git"
APP_DIR="/home/ec2-user/un-cvnt-jams"

echo "=== V1 Deploy: Sending SSM Command ==="

CMD_ID=$(aws ssm send-command \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --comment "V1 Deploy — deterministic clone, build, restart, test" \
  --timeout-seconds 3600 \
  --parameters "commands=[
    \"set -euo pipefail\",
    \"echo '[DEPLOY] Setting up swap...'\",
    \"if ! swapon -s | grep -q /swapfile; then sudo dd if=/dev/zero of=/swapfile bs=1M count=2048; sudo chmod 600 /swapfile; sudo mkswap /swapfile; sudo swapon /swapfile; fi\",
    \"echo '[DEPLOY] whoami:' && whoami && id\",
    \"echo '[DEPLOY] Stopping worker...'\",
    \"sudo systemctl stop publishing-worker || true\",
    \"echo '[DEPLOY] Removing old app dir...'\",
    \"sudo rm -rf $APP_DIR\",
    \"echo '[DEPLOY] Creating app dir...'\",
    \"sudo install -d -m 0755 -o ec2-user -g ec2-user $APP_DIR\",
    \"echo '[DEPLOY] Cloning repo as ec2-user...'\",
    \"sudo -u ec2-user -H bash -lc 'set -euo pipefail; git clone --depth 1 $REPO_URL $APP_DIR'\",
    \"echo '[DEPLOY] Setting up venv and deps...'\",
    \"sudo -u ec2-user -H bash -lc 'set -euo pipefail; cd $APP_DIR; python3 -m venv venv; source venv/bin/activate; pip install -U pip; pip install -r requirements.txt'\",
    \"echo '[DEPLOY] Configuring .env...'\",
    \"sudo -u ec2-user -H bash -lc 'set -euo pipefail; cd $APP_DIR; (grep -q \\\"^NOVNC_IMAGE_URI=\\\" .env 2>/dev/null && sed -i \\\"s|^NOVNC_IMAGE_URI=.*|NOVNC_IMAGE_URI=novnc-lite:latest|\\\" .env) || echo \\\"NOVNC_IMAGE_URI=novnc-lite:latest\\\" >> .env'\",
    \"echo '[DEPLOY] Building novnc-lite Docker image...'\",
    \"cd $APP_DIR/infra/docker/novnc-lite && sudo docker build -t novnc-lite:latest .\",
    \"echo '[DEPLOY] Restarting worker...'\",
    \"sudo systemctl daemon-reload\",
    \"sudo systemctl restart publishing-worker\",
    \"echo '[DEPLOY] Queuing test job...'\",
    \"sudo -u ec2-user -H bash -lc 'set -euo pipefail; cd $APP_DIR; source venv/bin/activate; python3 scripts/queue_test_job.py'\",
    \"echo '[DEPLOY] Waiting for job execution...'\",
    \"sleep 25\",
    \"echo '[DEPLOY] Worker logs:'\",
    \"sudo journalctl -u publishing-worker -n 300 --no-pager\",
    \"echo '[DEPLOY] Complete.'\"
  ]" \
  --query "Command.CommandId" \
  --output text)

if [[ -z "$CMD_ID" ]]; then
  echo "ERROR: Failed to get CommandId from SSM"
  exit 1
fi

echo "CommandId: $CMD_ID"
echo "=== Polling SSM Command Status ==="

while true; do
  RESULT=$(aws ssm get-command-invocation \
    --region "$REGION" \
    --command-id "$CMD_ID" \
    --instance-id "$INSTANCE_ID" \
    --output json 2>/dev/null || echo '{"Status":"Pending"}')

  STATUS=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('Status','Unknown'))")
  
  echo "Status: $STATUS"

  if [[ "$STATUS" == "Success" ]]; then
    echo "=== SSM Command Succeeded ==="
    echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print('--- STDOUT ---'); print(d.get('StandardOutputContent','(empty)'))"
    echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print('--- STDERR ---'); print(d.get('StandardErrorContent','(empty)'))"
    exit 0
  elif [[ "$STATUS" == "Failed" ]] || [[ "$STATUS" == "Cancelled" ]] || [[ "$STATUS" == "TimedOut" ]]; then
    echo "=== SSM Command Failed: $STATUS ==="
    echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print('--- STDOUT ---'); print(d.get('StandardOutputContent','(empty)'))"
    echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print('--- STDERR ---'); print(d.get('StandardErrorContent','(empty)'))"
    exit 1
  fi

  sleep 10
done
