#!/usr/bin/env python3
"""Monitor GoLogin free tier usage."""

import os
import time
from pathlib import Path
import json

USAGE_FILE = Path("pipeline_output/gologin_usage.json")

def load_usage():
    """Load usage data."""
    if USAGE_FILE.exists():
        with open(USAGE_FILE) as f:
            return json.load(f)
    return {"monthly_launches": 0, "last_reset": time.time()}

def save_usage(usage):
    """Save usage data."""
    # Ensure dir exists
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USAGE_FILE, 'w') as f:
        json.dump(usage, f)

def record_launch():
    """Record a profile launch."""
    usage = load_usage()
    
    # Reset monthly counter if needed
    current_month = time.gmtime(time.time()).tm_mon
    last_month = time.gmtime(usage.get("last_reset", 0)).tm_mon
    
    if current_month != last_month:
        usage["monthly_launches"] = 0
        usage["last_reset"] = time.time()
    
    usage["monthly_launches"] += 1
    save_usage(usage)
    
    # Warn if approaching limit
    if usage["monthly_launches"] >= 80:  # 80% of 100 limit
        print(f"⚠️  GoLogin usage: {usage['monthly_launches']}/100 launches this month")
    
    return usage["monthly_launches"] <= 100

if __name__ == "__main__":
    usage = load_usage()
    print(f"Current Usage: {usage['monthly_launches']}/100 launches")
