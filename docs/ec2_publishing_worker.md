# EC2 Publishing Worker Deployment

## Prerequisites
- **EC2 Instance**: Amazon Linux 2023 t3.micro.
- **Python 3.11**: Required for union syntax support.
- **Access**: SSH key (`key_pair_1.pem`).

---

## 1. Connect to EC2
```bash
cd /Users/franciscoterpolilli/Downloads
chmod 400 key_pair_1.pem
ssh -i key_pair_1.pem ec2-user@ec2-98-80-140-151.compute-1.amazonaws.com
```

## 2. Environment Setup (EC2)
Ensure Python 3.11 is installed and the virtual environment is set up.

```bash
sudo dnf install -y python3.11 git
cd /home/ec2-user/un-cvnt-jams

# Recreate venv with Python 3.11
rm -rf venv
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. Database Migration
Apply schema changes for `LaunchGroup` quotas (Strict Counters).

```bash
# Ensure you are in venv
source venv/bin/activate
export PYTHONPATH=src

# Run migration
alembic upgrade head
```

## 4. Install Systemd Service (Timer + Service)
Install the **oneshot** service and the **timer** to trigger it every 5 minutes.

```bash
# Copy unit files
sudo cp infra/systemd/publishing-worker.service /etc/systemd/system/
sudo cp infra/systemd/publishing-worker.timer /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and Start Timer
sudo systemctl enable --now publishing-worker.timer

# (Optional) Run service immediately to test
sudo systemctl start publishing-worker.service
```

## 5. Verification
Check the status and logs.

```bash
# Check timer status
sudo systemctl status publishing-worker.timer

# Check service status (might be inactive if waiting for timer)
sudo systemctl status publishing-worker.service

# View Logs
sudo journalctl -u publishing-worker -n 50 --no-pager
```

## 6. Smoke Test
Run the smoke test script to validate DB connectivity and Quota Enforcement.

```bash
source venv/bin/activate
export PYTHONPATH=src
python scripts/smoke_test_worker.py
```
**Expected Output**: `[SmokeTest] PASSED.`

---

## Rollback / Restart
If you deploy new code:
```bash
# Sync files (from local machine)
# rsync ...

# On EC2:
sudo systemctl daemon-reload
sudo systemctl restart publishing-worker.timer
```
