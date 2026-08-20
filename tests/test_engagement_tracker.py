"""
Unit tests for engagement_tracker.py.

These tests build their own temporary data/*.json files rather than
touching real data, so they're safe to run anytime without wiping out
real submissions.

Run with: python -m unittest tests.test_engagement_tracker
(or python -m unittest discover, if this sits in your tests/ folder)
"""

import unittest
import json
import os
import shutil
from datetime import datetime

from engagement_tracker import get_engagement_summary

TEST_DATA_DIR = "data"


class TestEngagementTracker(unittest.TestCase):

    def setUp(self):
        """
        Runs before EVERY test. Builds a fresh, known set of tasks and
        submissions for a fake patient, so each test starts from a
        predictable state instead of depending on leftover data from
        a previous test.
        """
        os.makedirs(TEST_DATA_DIR, exist_ok=True)

        self.patient_id = "99992024"

        tasks = {
            "task_A": {"assigned_patient_id": self.patient_id, "due_date": "2026-01-05",
                       "title": "t", "description": "d", "clinic_id": "c1", "attachment_path": None, "created_at": ""},
            "task_B": {"assigned_patient_id": self.patient_id, "due_date": "2026-01-10",
                       "title": "t", "description": "d", "clinic_id": "c1", "attachment_path": None, "created_at": ""},
            "task_C": {"assigned_patient_id": self.patient_id, "due_date": "2026-01-15",
                       "title": "t", "description": "d", "clinic_id": "c1", "attachment_path": None, "created_at": ""},
        }
        with open(os.path.join(TEST_DATA_DIR, "health_tasks.json"), "w") as f:
            json.dump(tasks, f)

        # task_A: submitted ON TIME (before due date)
        # task_B: submitted LATE (after due date)
        # task_C: NOT submitted at all
        submissions = {
            f"{self.patient_id}_task_A": {
                "patient_id": self.patient_id, "task_id": "task_A",
                "timestamp": "2026-01-04T09:00:00", "review_status": "Pending",
                "file_path": "x", "reviewer_id": None, "review_notes": None,
                "notification_sent": False,
            },
            f"{self.patient_id}_task_B": {
                "patient_id": self.patient_id, "task_id": "task_B",
                "timestamp": "2026-01-12T09:00:00", "review_status": "Pending",
                "file_path": "x", "reviewer_id": None, "review_notes": None,
                "notification_sent": False,
            },
        }
        with open(os.path.join(TEST_DATA_DIR, "task_submissions.json"), "w") as f:
            json.dump(submissions, f)

    def test_total_tasks_counts_all_assigned(self):
        summary = get_engagement_summary(self.patient_id)
        self.assertEqual(summary["total_tasks"], 3)

    def test_completed_tasks_counts_any_submission(self):
        # Both task_A (on time) and task_B (late) count as "completed" -
        # completion just means "a file was submitted", regardless of
        # timing.
        summary = get_engagement_summary(self.patient_id)
        self.assertEqual(summary["completed_tasks"], 2)

    def test_on_time_tasks_only_counts_punctual_ones(self):
        # Only task_A was on time - task_B was late, task_C wasn't
        # submitted at all.
        summary = get_engagement_summary(self.patient_id)
        self.assertEqual(summary["on_time_tasks"], 1)

    def test_completion_rate_calculation(self):
        # 2 out of 3 tasks completed = 66.7%
        summary = get_engagement_summary(self.patient_id)
        self.assertAlmostEqual(summary["completion_rate"], 66.7, places=1)

    def test_on_time_rate_calculation(self):
        # 1 out of 3 tasks on time = 33.3%
        summary = get_engagement_summary(self.patient_id)
        self.assertAlmostEqual(summary["on_time_rate"], 33.3, places=1)

    def test_streak_breaks_on_late_submission(self):
        # Chronologically: task_A (on time) -> task_B (late) -> task_C
        # (not submitted). The streak counts backwards from the most
        # recent task, so it should be 0 here because the LAST task
        # wasn't even submitted.
        summary = get_engagement_summary(self.patient_id)
        self.assertEqual(summary["current_on_time_streak"], 0)

    def test_patient_with_no_tasks_gets_zero_not_error(self):
        # A brand new patient with nothing assigned should get clean
        # zeros, not a crash from dividing by zero.
        summary = get_engagement_summary("00000000")
        self.assertEqual(summary["total_tasks"], 0)
        self.assertEqual(summary["completion_rate"], 0.0)
        self.assertEqual(summary["current_on_time_streak"], 0)

    def tearDown(self):
        """Runs after every test - clean up the test data files."""
        for filename in ["health_tasks.json", "task_submissions.json"]:
            path = os.path.join(TEST_DATA_DIR, filename)
            if os.path.exists(path):
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
