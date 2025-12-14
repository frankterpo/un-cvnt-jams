#!/usr/bin/env python3
import sys
import os
from datetime import datetime, timezone
from sqlalchemy import text

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from agent.db.base import SessionLocal
from agent.jobs.publishing import PublishingJob
from agent.services.launch_group_service import LaunchGroupService
from agent.db.models import PublishingRun, LaunchGroup

def smoke_test():
    print("[SmokeTest] Starting...")
    session = SessionLocal()
    try:
        # 1. Verify DB Access
        print("[SmokeTest] Checking DB Connectivity...")
        session.execute(text("SELECT 1"))
        print("[SmokeTest] DB Connected.")
        
        print("[SmokeTest] Setting up test LaunchGroup and Run...")
        group = LaunchGroup(name="SmokeTestGroup", max_runs_per_day=0) # Zero limit to test blocking
        session.add(group)
        session.commit()
        # Fetch group ID
        group_id = session.execute(text("SELECT id FROM launch_groups WHERE name='SmokeTestGroup' ORDER BY id DESC LIMIT 1")).scalar()
        
        # Test 1: Quota Block
        print(f"[SmokeTest] Testing Quota Block (Group {group_id} has limit 0)...")
        can_run = LaunchGroupService.can_execute_run(session, group_id)
        if not can_run:
            print("[SmokeTest] Quota enforcement worked: Run denied.")
        else:
            print("[SmokeTest] FAIL: Quota enforcement failed (allowed run on 0 limit).")
            return 1
            
        # Cleanup
        # Use ORM delete to ensure session state stays consistent
        session.delete(group)
        session.commit()
        print("[SmokeTest] Cleanup complete.")
        
    except Exception as e:
        print(f"[SmokeTest] ERROR: {e}")
        return 1
    finally:
        session.close()
    
    print("[SmokeTest] PASSED.")
    return 0

if __name__ == "__main__":
    if "src" not in sys.path[-1]:
         # Rough check if path is set
         pass
    sys.exit(smoke_test())
