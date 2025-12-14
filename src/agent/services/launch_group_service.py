from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from loguru import logger
from agent.db.models import LaunchGroup

class LaunchGroupService:
    """
    Service for enforcing LaunchGroup quotas using stored counters and windows.
    Enforces Strict Limits:
    - Max Runs Per Month
    - Max Runs Per Day
    - Max Concurrent Runs
    """

    @staticmethod
    def get_launch_group(session: Session, launch_group_id: int) -> Optional[LaunchGroup]:
        return session.get(LaunchGroup, launch_group_id)

    @staticmethod
    def can_execute_run(session: Session, launch_group_id: int) -> bool:
        """
        Checks if a run can be executed. Resets windows if expired.
        Returns True if allowed.
        """
        # Lock row for update to ensure safe counter access?
        # For simplicity in this scope, we rely on atomic commit or sequential checks.
        # But `with_for_update()` is safer.
        group = session.execute(
            select(LaunchGroup).where(LaunchGroup.id == launch_group_id).with_for_update()
        ).scalar_one_or_none()
        
        if not group:
            logger.warning(f"Launch group {launch_group_id} not found. Denying run.")
            return False

        now = datetime.now(timezone.utc)
        
        # 1. Check/Reset Day Window
        if group.day_window_start is None or (now - group.day_window_start).days >= 1 or group.day_window_start.date() != now.date():
             # Simple reset logic: if stored date is different day, reset.
             # Or strict 24h window? User said "per day", usually means calendar day or rolling 24h.
             # "day_window_start" implies we track the start.
             # Let's align on Calendar Day UTC for simplicity and consistency.
             if group.day_window_start is None or group.day_window_start.date() < now.date():
                 logger.info(f"Resetting daily counter for group {group.name}")
                 group.current_day_run_count = 0
                 group.day_window_start = now
        
        # 2. Check/Reset Month Window
        if group.month_window_start is None or group.month_window_start.month != now.month or group.month_window_start.year != now.year:
             logger.info(f"Resetting monthly counter for group {group.name}")
             group.current_month_run_count = 0
             group.month_window_start = now

        # 3. Check Concurrent
        # Concurrent runs should ideally be self-correcting or checked via active runs count if we don't trust the counter.
        # But we were asked to use counters. We will assume on_run_finished decrements it.
        # Auto-reset if negative?
        if group.current_concurrent_runs < 0:
            group.current_concurrent_runs = 0

        # Validate Limits
        if group.max_concurrent_runs is not None and group.current_concurrent_runs >= group.max_concurrent_runs:
            logger.warning(f"Quota Hit: Max concurrent runs ({group.max_concurrent_runs}) reached for group {group.name}")
            return False

        if group.max_runs_per_day is not None and group.current_day_run_count >= group.max_runs_per_day:
            logger.warning(f"Quota Hit: Max daily runs ({group.max_runs_per_day}) reached for group {group.name}")
            return False

        if group.max_runs_per_month is not None and group.current_month_run_count >= group.max_runs_per_month:
            logger.warning(f"Quota Hit: Max monthly runs ({group.max_runs_per_month}) reached for group {group.name}")
            return False

        return True

    @staticmethod
    def on_run_started(session: Session, launch_group_id: int):
        """Increments counters."""
        group = session.execute(
            select(LaunchGroup).where(LaunchGroup.id == launch_group_id).with_for_update()
        ).scalar_one_or_none()
        
        if group:
            group.current_concurrent_runs += 1
            group.current_day_run_count += 1
            group.current_month_run_count += 1
            session.add(group)
            # Commit should be handled by caller usually, but to lock effectively we need to be in same transaction.

    @staticmethod
    def on_run_finished(session: Session, launch_group_id: int):
        """Decrements concurrent counter."""
        group = session.execute(
            select(LaunchGroup).where(LaunchGroup.id == launch_group_id).with_for_update()
        ).scalar_one_or_none()
        
        if group:
            group.current_concurrent_runs = max(0, group.current_concurrent_runs - 1)
            session.add(group)
