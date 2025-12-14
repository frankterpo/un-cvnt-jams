#!/usr/bin/env python3
import sys
import os
from datetime import datetime, timezone
from sqlalchemy import select, or_, and_

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from agent.db.base import SessionLocal
from agent.db.models import PublishingRun
from agent.jobs.publishing import PublishingJob
from loguru import logger

MAX_RUNS_PER_INVOCATION = 10

def has_pending_runs(session) -> bool:
    now = datetime.now(timezone.utc)
    # Check for pending, retry, or scheduled <= now
    # We use the same logic as PublishingRunService.get_pending_runs usually, 
    # but here we just want to know if we should START the job.
    
    # "Pending work" means rows where status in ["PENDING", "SCHEDULED", "RETRY"]
    # AND (scheduled_at IS NULL OR scheduled_at <= now)
    
    stmt = select(PublishingRun).where(
        PublishingRun.status.in_(["PENDING", "SCHEDULED", "RETRY"]),
        or_(PublishingRun.scheduled_at == None, PublishingRun.scheduled_at <= now)
    ).limit(1)
    
    result = session.execute(stmt).scalar_one_or_none()
    return result is not None

def main() -> int:
    # Setup logger to stdout/stderr for systemd
    logger.remove()
    logger.add(sys.stdout, level="INFO")
    
    with SessionLocal() as session:
        if not has_pending_runs(session):
            print("[worker] No pending runs, exiting")
            return 0

    try:
        job = PublishingJob()
        result = job.process_pending_runs(limit=MAX_RUNS_PER_INVOCATION)
        print(f"[worker] Result: {result}")
    except Exception as exc:
        print(f"[worker] ERROR: {exc}", file=sys.stderr)
        logger.exception("Worker failed")
        return 1

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
