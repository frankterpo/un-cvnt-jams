import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from agent.services.launch_group_service import LaunchGroupService
from agent.db.models import LaunchGroup

class TestLaunchGroupService(unittest.TestCase):
    def setUp(self):
        self.session = MagicMock()
        self.launch_group = LaunchGroup(
            id=1,
            name="Test Group",
            max_runs_per_month=100,
            max_runs_per_day=10,
            max_concurrent_runs=2,
            current_month_run_count=0,
            current_day_run_count=0,
            current_concurrent_runs=0,
            month_window_start=datetime.now(timezone.utc),
            day_window_start=datetime.now(timezone.utc)
        )
        # Mock session.execute to return our group
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = self.launch_group
        self.session.execute.return_value = mock_result

    def test_can_execute_run_all_pass(self):
        result = LaunchGroupService.can_execute_run(self.session, 1)
        self.assertTrue(result)

    def test_can_execute_limit_hit(self):
        self.launch_group.current_concurrent_runs = 2
        result = LaunchGroupService.can_execute_run(self.session, 1)
        self.assertFalse(result)

    def test_window_reset(self):
        # Simulate yesterday
        yesterday = datetime.now(timezone.utc) - timedelta(days=2)
        self.launch_group.day_window_start = yesterday
        self.launch_group.current_day_run_count = 10 # Limit reached for yesterday
        
        # Should reset and allow run
        result = LaunchGroupService.can_execute_run(self.session, 1)
        self.assertTrue(result)
        self.assertEqual(self.launch_group.current_day_run_count, 0)
        self.assertTrue(self.launch_group.day_window_start.date() == datetime.now(timezone.utc).date())

    def test_on_run_started(self):
        LaunchGroupService.on_run_started(self.session, 1)
        self.assertEqual(self.launch_group.current_concurrent_runs, 1)
        self.assertEqual(self.launch_group.current_day_run_count, 1)

    def test_on_run_finished(self):
        self.launch_group.current_concurrent_runs = 1
        LaunchGroupService.on_run_finished(self.session, 1)
        self.assertEqual(self.launch_group.current_concurrent_runs, 0)
