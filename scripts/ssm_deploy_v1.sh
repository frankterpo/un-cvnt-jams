#!/usr/bin/env bash
set -euo pipefail

# === Antigravity V1 SSM Deploy Script ===
# Guardrails:
# 1. Timer Freeze: stop/disable timer & service prevents mid-deploy restarts.
# 2. Shallow Clone: depth 1, clean wipe of target dir.
# 3. EC2-User Verify: all verifications run as service user.
# 4. Import Sanity: proves lazy imports work before starting service.

REGION="us-east-1"
INSTANCE_ID="i-0aff9502a7ecee0e3"
REPO_URL="https://github.com/frankterpo/un-cvnt-jams.git"

echo "=== Antigravity V1 Deploy: Sending SSM Command ==="

CMD_ID=$(aws ssm send-command \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --comment "V1 Deploy (shallow clone + timer control + verify lazy imports)" \
  --timeout-seconds 3600 \
  --parameters "commands=[
    \"set -euo pipefail\",

    \"echo '[DEPLOY] START \$(date -Is)'\",
    \"echo '[DEPLOY] whoami=\$(whoami)'\",
    
    \"echo '[DEPLOY] Phase 2: Stop timer/service'\",
    \"systemctl stop publishing-worker.timer || true\",
    \"systemctl disable publishing-worker.timer || true\",
    \"systemctl stop publishing-worker.service || true\",
    \"systemctl reset-failed publishing-worker.service || true\",

    \"echo '[DEPLOY] Preflight disk/mem'\",
    \"AVAIL_KB=\$(df --output=avail -k / | tail -n 1 | tr -d ' ')\",
    \"if [ \\\"\$AVAIL_KB\\\" -lt 2500000 ]; then echo '[DEPLOY] Low disk (<2.5GB). Pruning docker...'; docker system prune -af || true; fi\",

    \"APP=/home/ec2-user/un-cvnt-jams\",
    \"echo '[DEPLOY] Shallow clone as ec2-user'\",
    \"rm -rf \\\"\$APP\\\"\",
    \"sudo -u ec2-user -H bash -lc 'set -euo pipefail; cd /home/ec2-user; \
      git clone --depth 1 --branch main $REPO_URL un-cvnt-jams || \
      (echo CLONE_RETRY; sleep 3; rm -rf un-cvnt-jams; git clone --depth 1 --branch main $REPO_URL un-cvnt-jams)'\",

    \"echo '[DEPLOY] Venv + deps'\",
    \"sudo -u ec2-user -H bash -lc 'APP=/home/ec2-user/un-cvnt-jams; set -euo pipefail; cd \$APP; python3 -m venv venv; \
      source venv/bin/activate; pip install -U pip; \
      PIP_NO_CACHE_DIR=1 pip install -r requirements.txt'\",

    \"echo '[DEPLOY] Configure .env'\",
    \"sudo -u ec2-user -H bash -lc 'APP=/home/ec2-user/un-cvnt-jams; set -euo pipefail; cd \$APP; \
      echo NOVNC_IMAGE_URI=novnc-lite:latest >> .env; \
      echo "DATABASE_URL=postgresql+psycopg2://socialagent_admin:P1rulo007%21@social-agent-db.cej60cw482tv.us-east-1.rds.amazonaws.com:5432/social_agent" >> .env'\",

    \"echo '[DEPLOY] Phase 1 Verification: Test Lazy Imports'\",
    \"sudo -u ec2-user -H bash -lc 'APP=/home/ec2-user/un-cvnt-jams; set -euo pipefail; cd \$APP; source venv/bin/activate; \
      python3 -c \\\"import sys; sys.path.append(\\\\\\\"src\\\\\\\"); from agent.workflow import run_cycle_single; print(\\\\\\\"Workflow Import OK\\\\\\\")\\\"; \
      python3 -c \\\"import sys; sys.path.append(\\\\\\\"src\\\\\\\"); from agent.jobs.publishing import PublishingJob; print(\\\\\\\"Job Import OK\\\\\\\")\\\"'\",

    \"echo '[DEPLOY] Phase 2: Start Timer'\",
    \"systemctl daemon-reload || true\",
    \"systemctl enable --now publishing-worker.timer\",

    \"echo '[DEPLOY] Diagnostics'\",
    \"systemctl status publishing-worker.timer --no-pager\",
    \"sleep 5\",
    \"journalctl -u publishing-worker.service -n 50 --no-pager || true\",

    \"echo '[DEPLOY] END \$(date -Is)'\"
  ]" \
  --query "Command.CommandId" \
  --output text)

if [[ -z "$CMD_ID" ]]; then
  echo "ERROR: Failed to get CommandId"
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
  
  # Print tail of output for progress
  echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); out=d.get('StandardOutputContent',''); print(out[-500:] if out else '')"

  if [[ "$STATUS" == "Success" ]]; then
    echo "=== SSM Command Succeeded ==="
    exit 0
  elif [[ "$STATUS" == "Failed" ]] || [[ "$STATUS" == "Cancelled" ]] || [[ "$STATUS" == "TimedOut" ]]; then
    echo "=== SSM Command Failed: $STATUS ==="
    echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print('--- STDERR ---'); print(d.get('StandardErrorContent',''))"
    exit 1
  fi
  sleep 10
done
