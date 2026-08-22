"""
Unit tests for Engagement Points and appointment attendance tracking
(Section E completion).
"""

import unittest
import json
import os

from models.engagement_tracker import get_engagement_summary
from models.appointment import Appointment

DATA_DIR = "data"


class TestEngagementPointsAndAttendance(unittest.TestCase):

    def setUp(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.patient_id = "88881234"

        with open(os.path.join(DATA_DIR, "health_tasks.json"), "w") as f:
            json.dump({}, f)
        with open(os.path.join(DATA_DIR, "task_submissions.json"), "w") as f:
            json.dump({}, f)
        with open(os.path.join(DATA_DIR, "appointments.json"), "w") as f:
            json.dump({}, f)

    def test_no_data_gives_zero_points_not_error(self):
        summary = get_engagement_summary(self.patient_id)
        self.assertEqual(summary["engagement_points"], 0)
        self.assertEqual(summary["appointment_attendance_rate"], 0.0)
        self.assertEqual(summary["appointments_marked"], 0)

    def test_attended_appointment_earns_points(self):
        Appointment("appt_1", self.patient_id, "clinic1",
                    "2020-01-01", "10:00", "Check-up").save()
        Appointment.mark_attendance("appt_1", True)

        summary = get_engagement_summary(self.patient_id)
        self.assertEqual(summary["appointments_attended"], 1)
        self.assertEqual(summary["appointments_marked"], 1)
        self.assertEqual(summary["appointment_attendance_rate"], 100.0)
        self.assertEqual(summary["engagement_points"], 5)

    def test_missed_appointment_earns_no_points(self):
        Appointment("appt_1", self.patient_id, "clinic1",
                    "2020-01-01", "10:00", "Check-up").save()
        Appointment.mark_attendance("appt_1", False)

        summary = get_engagement_summary(self.patient_id)
        self.assertEqual(summary["appointments_attended"], 0)
        self.assertEqual(summary["appointments_marked"], 1)
        self.assertEqual(summary["appointment_attendance_rate"], 0.0)
        self.assertEqual(summary["engagement_points"], 0)

    def test_unmarked_past_appointment_does_not_count_as_missed(self):
        Appointment("appt_1", self.patient_id, "clinic1",
                    "2020-01-01", "10:00", "Check-up").save()

        summary = get_engagement_summary(self.patient_id)
        self.assertEqual(summary["appointments_marked"], 0)
        self.assertEqual(summary["appointment_attendance_rate"], 0.0)

    def test_upcoming_appointment_excluded_from_attendance_stats(self):
        from datetime import datetime, timedelta
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        Appointment("appt_future", self.patient_id, "clinic1",
                    tomorrow, "10:00", "Future check-up").save()

        summary = get_engagement_summary(self.patient_id)
        self.assertEqual(summary["appointments_marked"], 0)

    def test_mixed_attendance_calculates_correct_rate(self):
        Appointment("appt_1", self.patient_id, "clinic1",
                    "2020-01-01", "10:00", "Visit 1").save()
        Appointment("appt_2", self.patient_id, "clinic1",
                    "2020-02-01", "10:00", "Visit 2").save()
        Appointment("appt_3", self.patient_id, "clinic1",
                    "2020-03-01", "10:00", "Visit 3").save()
        Appointment.mark_attendance("appt_1", True)
        Appointment.mark_attendance("appt_2", True)
        Appointment.mark_attendance("appt_3", False)

        summary = get_engagement_summary(self.patient_id)
        self.assertEqual(summary["appointments_attended"], 2)
        self.assertEqual(summary["appointments_marked"], 3)
        self.assertAlmostEqual(summary["appointment_attendance_rate"], 66.7, places=1)
        self.assertEqual(summary["engagement_points"], 10)

    def tearDown(self):
        for filename in ["health_tasks.json", "task_submissions.json", "appointments.json"]:
            path = os.path.join(DATA_DIR, filename)
            if os.path.exists(path):
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
    
