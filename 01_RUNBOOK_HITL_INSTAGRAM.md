# Instagram upload on EC2 — HITL login + run artifacts (operator runbook)

This runbook assumes:
- EC2 instance reachable via SSM Session Manager
- Chrome + chromedriver installed on the instance
- Repo path: `/home/ec2-user/un-cvnt-jams`
- Instagram Chrome profile dir: `/home/ec2-user/un-cvnt-jams/chrome-profiles/instagram-main`

> Security: do **not** paste full HTML dumps into chat. Use keyword greps only.

---

## 0) Start an SSM shell session
From your laptop:

```bash
REGION=us-east-1
INSTANCE_ID=i-0aff9502a7ecee0e3
aws ssm start-session --region "$REGION" --target "$INSTANCE_ID"
```

You should land in a shell like `sh-5.2$`.

---

## 1) Run the upload in a “run folder” (recommended)
On the instance shell:

```bash
APP=/home/ec2-user/un-cvnt-jams
PROFILE_DIR="$APP/chrome-profiles/instagram-main"
VIDEO="$APP/sample_videos/test_tiktok.mp4"

cd "$APP"
sudo -u ec2-user -H bash -lc "./scripts/run_instagram_upload_run.sh   --video '$VIDEO'   --caption 'UCJ_IG_test'   --profile-dir '$PROFILE_DIR'   --post-type reel   --interactive-login"
```

This will print:
- `RUN_ID=...`
- `DEBUG_DIR=/tmp/ig_runs/<RUN_ID>/`
- `run.log` path

In a **second** SSM session, tail:

```bash
tail -f "/tmp/ig_runs/<RUN_ID>/run.log"
```

---

## 2) If it needs human login (Option A: CDP + Screencast)
When login is required, the log should print something like:

- “Starting interactive login via CDP”
- “Port-forward this: …”
- “Open: http://127.0.0.1:9222”
- “Click inspect → Show Screencast”

### 2.1 Start port forwarding (from your laptop)
In a new local terminal:

```bash
aws ssm start-session   --region us-east-1   --target i-0aff9502a7ecee0e3   --document-name AWS-StartPortForwardingSession   --parameters '{"portNumber":["9222"],"localPortNumber":["9222"]}'
```

### 2.2 Open DevTools locally
Open in your browser:

- `http://127.0.0.1:9222`

Click **inspect** on the Instagram tab, then:
- DevTools command menu: `Ctrl+Shift+P`
- Type: `Show Screencast`
- Complete login / 2FA / checkpoint as needed

When done, leave the screencast open until the run logs “login detected” and proceeds.

---

## 3) Debug: make HTML artifacts readable to your SSM user
If you need to inspect HTML/screenshot dumps but your SSM user can’t read `/home/ec2-user/...`, copy artifacts into `/tmp`:

```bash
RUN_ID="<RUN_ID>"
APP=/home/ec2-user/un-cvnt-jams
sudo mkdir -p "/tmp/ig_runs/$RUN_ID"
sudo cp "$APP"/debug_instagram*.html "/tmp/ig_runs/$RUN_ID/" 2>/dev/null || true
sudo chmod a+r "/tmp/ig_runs/$RUN_ID/"debug_instagram*.html 2>/dev/null || true

ls -lah "/tmp/ig_runs/$RUN_ID/"
```

Fast classification (safe grep):

```bash
FILE=$(ls -t /tmp/ig_runs/$RUN_ID/debug_instagram*.html | head -n1)
grep -iE "accounts/login|challenge|checkpoint|two-factor|captcha|robot|suspended" -n "$FILE" | head -n 80
grep -iE ""userId"[: ]*0|"userId"[: ]*[1-9]" -n "$FILE" | head -n 20
```

- `userId: 0` → logged out
- `accounts/login` → login page
- `challenge|checkpoint` → checkpoint flow

---

## 4) Collect artifacts (zip)
After a run:

```bash
RUN_ID="<RUN_ID>"
ls -lah "/tmp/ig_runs/$RUN_ID/"
ls -lah "/tmp/ig_runs/$RUN_ID.zip" 2>/dev/null || true
```

---

## 5) Common pitfalls
- **Running instance commands on your Mac**: anything referencing `/home/ec2-user/...` must run in the SSM instance shell.
- **Permissions**: your interactive SSM user may not read `/home/ec2-user/...`; use `sudo -u ec2-user` or copy to `/tmp`.
- **SingletonLock**: always remove `Singleton{Lock,Socket,Cookie}` before reusing the profile.
- **/dev/shm**: if chrome crashes, confirm `--disable-dev-shm-usage` is set and check memory/disk.
