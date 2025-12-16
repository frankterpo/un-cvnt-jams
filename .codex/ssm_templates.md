# SSM templates (copy/paste)

## Assumptions
- REGION=us-east-1
- INSTANCE_ID=i-0aff9502a7ecee0e3
- APP=/home/ec2-user/un-cvnt-jams

## Rule: avoid parentheses in any shell lines
SSM on this box has repeatedly failed on lines containing "(" or ")". Use plain text.

## Generic send-command + fetch result
REGION=us-east-1
INSTANCE_ID=i-0aff9502a7ecee0e3

COMMAND_ID="$(aws ssm send-command \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --comment "TODO" \
  --max-concurrency "1" \
  --max-errors "0" \
  --parameters 'commands=[
    "set -euo pipefail",
    "cd /home/ec2-user/un-cvnt-jams",
    ". .venv/bin/activate",
    "df -h /",
    "echo TODO RUN"
  ]' \
  --query "Command.CommandId" \
  --output text)"

aws ssm get-command-invocation \
  --region "$REGION" \
  --instance-id "$INSTANCE_ID" \
  --command-id "$COMMAND_ID" \
  --query '{Status:Status,RC:ResponseCode,Stdout:StandardOutputContent,Stderr:StandardErrorContent}' \
  --output json
