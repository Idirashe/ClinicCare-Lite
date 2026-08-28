"""
Tests: operational analytics module (Section C) - Member 4's own code,
covering both correct calculations and the privacy rule that
operational analytics must never expose one patient's data to another.
"""

import unittest
import json
import os
from datetime import datetime, timedelta

from tests.test_data_reset import reset_to_empty_data
from utils import analytics


def _write_json(filename, data):
    with open(os.path.join("data", filename), "w") as f:
        json.dump(data, f, indent=4)


class TestTaskCompletionRate(unittest.TestCase):

    def setUp(self):
        reset_to_empty_data()

    def test_completion_rate_with_no_tasks_is_zero(self):
        # No tasks at all for this clinic - should be 0.0, not a
        # division-by-zero crash.
        self.assertEqual(analytics.task_completion_rate("clinic_01"), 0.0)

    def test_completion_rate_calculates_correctly(self):
        _write_json("health_tasks.json", {
            "task_0001": {"clinic_id": "clinic_01", "assigned_patient_id": "p1",
                          "due_date": "2026-01-01", "created_at": "2026-01-01T00:00:00"},
            "task_0002": {"clinic_id": "clinic_01", "assigned_patient_id": "p2",
                          "due_date": "2026-01-01", "created_at": "2026-01-01T00:00:00"},
        })
        _write_json("task_submissions.json", {
            "p1_task_0001": {"timestamp": "2026-01-01T00:00:00",
                             "review_status": "Reviewed - Normal"},
            # p2_task_0002 was never submitted.
        })
        # 1 of 2 tasks submitted = 50.0%
        self.assertEqual(analytics.task_completion_rate("clinic_01"), 50.0)

    def test_only_counts_tasks_for_the_requested_clinic(self):
        """
        PRIVACY/ISOLATION CHECK: a task belonging to a DIFFERENT clinic
        must never affect this clinic's completion rate.
        """
        _write_json("health_tasks.json", {
            "task_0001": {"clinic_id": "clinic_01", "assigned_patient_id": "p1",
                          "due_date": "2026-01-01", "created_at": "2026-01-01T00:00:00"},
            "task_9999": {"clinic_id": "clinic_99_other", "assigned_patient_id": "px",
                          "due_date": "2026-01-01", "created_at": "2026-01-01T00:00:00"},
        })
        _write_json("task_submissions.json", {})
        # Only clinic_01's ONE task should count -> 0% (not submitted),
        # and clinic_99_other's task must be completely invisible here.
        self.assertEqual(analytics.task_completion_rate("clinic_01"), 0.0)


class TestOverdueTaskCount(unittest.TestCase):

    def setUp(self):
        reset_to_empty_data()

    def test_overdue_task_counted(self):
        yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
        _write_json("health_tasks.json", {
            "task_0001": {"clinic_id": "clinic_01", "assigned_patient_id": "p1",
                          "due_date": yesterday, "created_at": "2026-01-01T00:00:00"},
        })
        _write_json("task_submissions.json", {})  # never submitted
        self.assertEqual(analytics.overdue_task_count("clinic_01"), 1)

    def test_future_task_not_counted_as_overdue(self):
        tomorrow = (datetime.now().date() + timedelta(days=1)).isoformat()
        _write_json("health_tasks.json", {
            "task_0001": {"clinic_id": "clinic_01", "assigned_patient_id": "p1",
                          "due_date": tomorrow, "created_at": "2026-01-01T00:00:00"},
        })
        _write_json("task_submissions.json", {})
        self.assertEqual(analytics.overdue_task_count("clinic_01"), 0)

    def test_submitted_task_not_counted_as_overdue_even_if_late(self):
        yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
        _write_json("health_tasks.json", {
            "task_0001": {"clinic_id": "clinic_01", "assigned_patient_id": "p1",
                          "due_date": yesterday, "created_at": "2026-01-01T00:00:00"},
        })
        _write_json("task_submissions.json", {
            "p1_task_0001": {"timestamp": datetime.now().isoformat(),
                             "review_status": "Pending"},
        })
        # It WAS submitted (even if late) so it's no longer "overdue" -
        # overdue specifically means "no submission at all yet".
        self.assertEqual(analytics.overdue_task_count("clinic_01"), 0)


class TestPendingReviews(unittest.TestCase):

    def setUp(self):
        reset_to_empty_data()

    def test_pending_and_followup_counted_reviewed_ones_are_not(self):
        _write_json("health_tasks.json", {
            "task_0001": {"clinic_id": "clinic_01", "assigned_patient_id": "p1",
                          "due_date": "2026-01-01", "created_at": "2026-01-01T00:00:00"},
            "task_0002": {"clinic_id": "clinic_01", "assigned_patient_id": "p2",
                          "due_date": "2026-01-01", "created_at": "2026-01-01T00:00:00"},
            "task_0003": {"clinic_id": "clinic_01", "assigned_patient_id": "p3",
                          "due_date": "2026-01-01", "created_at": "2026-01-01T00:00:00"},
        })
        _write_json("task_submissions.json", {
            "p1_task_0001": {"timestamp": "2026-01-01T00:00:00", "review_status": "Pending"},
            "p2_task_0002": {"timestamp": "2026-01-01T00:00:00", "review_status": "Needs Follow-up"},
            "p3_task_0003": {"timestamp": "2026-01-01T00:00:00", "review_status": "Reviewed - Normal"},
        })
        # Pending + Needs Follow-up = 2; Reviewed-Normal doesn't count.
        self.assertEqual(analytics.pending_reviews_count("clinic_01"), 2)


class TestAverageReviewTurnaround(unittest.TestCase):

    def setUp(self):
        reset_to_empty_data()

    def test_returns_none_when_no_reviewed_at_data_exists(self):
        """
        Confirms the honest "not available yet" behaviour documented in
        analytics.py: since the current submission schema has no
        reviewed_at field, this must return None rather than fabricate
        a number.
        """
        _write_json("health_tasks.json", {
            "task_0001": {"clinic_id": "clinic_01", "assigned_patient_id": "p1",
                          "due_date": "2026-01-01", "created_at": "2026-01-01T00:00:00"},
        })
        _write_json("task_submissions.json", {
            "p1_task_0001": {"timestamp": "2026-01-01T00:00:00",
                             "review_status": "Reviewed - Normal"},
        })
        self.assertIsNone(analytics.average_review_turnaround("clinic_01"))

    def test_calculates_correctly_once_reviewed_at_is_present(self):
        # Forward-looking test: once reviewed_at is added to the
        # schema, this proves the maths itself is correct.
        _write_json("health_tasks.json", {
            "task_0001": {"clinic_id": "clinic_01", "assigned_patient_id": "p1",
                          "due_date": "2026-01-01", "created_at": "2026-01-01T00:00:00"},
        })
        _write_json("task_submissions.json", {
            "p1_task_0001": {
                "timestamp": "2026-01-01T10:00:00",
                "reviewed_at": "2026-01-01T12:00:00",  # 2 hours later
                "review_status": "Reviewed - Normal",
            },
        })
        self.assertEqual(analytics.average_review_turnaround("clinic_01"), 2.0)


class TestNoShowRateByWeek(unittest.TestCase):

    def setUp(self):
        reset_to_empty_data()

    def test_week_with_no_marked_appointments_returns_none(self):
        _write_json("appointments.json", {})
        results = analytics.appointment_no_show_rate_by_week("clinic_01", weeks_back=2)
        # Every bucket should report None (no data), never a
        # misleading "0% no-shows" when nothing was actually recorded.
        for label, rate in results:
            self.assertIsNone(rate)

    def test_privacy_never_exposes_patient_identity(self):
        """
        Confirms the analytics summary dict never includes a patient_id
        or patient name anywhere in its output - only aggregate counts
        and rates, per the spec's privacy rule.
        """
        _write_json("appointments.json", {
            "appt_0001": {"clinic_id": "clinic_01", "patient_id": "12342024",
                          "date": "2026-01-01", "attended": False},
        })
        _write_json("health_tasks.json", {})
        _write_json("task_submissions.json", {})
        summary = analytics.build_analytics_summary("clinic_01")
        summary_text = json.dumps(summary)
        self.assertNotIn("12342024", summary_text)


if __name__ == "__main__":
    unittest.main()
