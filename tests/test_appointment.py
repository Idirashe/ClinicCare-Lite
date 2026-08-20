"""
Unit tests for models/appointment.py.

Uses temporary test data so real appointments.json is never touched.
"""

import unittest
import json
import os
from datetime import datetime, timedelta

from models.appointment import Appointment

TEST_DATA_DIR = "data"


class TestAppointment(unittest.TestCase):

    def setUp(self):
        os.makedirs(TEST_DATA_DIR, exist_ok=True)
        # Start with a clean, empty appointments file before each test.
        with open(os.path.join(TEST_DATA_DIR, "appointments.json"), "w") as f:
            json.dump({}, f)

        self.patient_id = "88882024"

    def test_save_and_retrieve_upcoming_appointment(self):
        # Build a date guaranteed to be in the future relative to
        # "now" (tomorrow), so this test doesn't become flaky over time.
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        appt = Appointment("appt_test1", self.patient_id, "clinic1",
                            tomorrow, "10:00", "Follow-up check-in")
        appt.save()

        upcoming = Appointment.get_upcoming_for_patient(self.patient_id)
        self.assertEqual(len(upcoming), 1)
        self.assertEqual(upcoming[0][1]["reason"], "Follow-up check-in")

    def test_past_appointment_excluded_from_upcoming(self):
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        appt = Appointment("appt_past", self.patient_id, "clinic1",
                            yesterday, "10:00", "Old appointment")
        appt.save()

        upcoming = Appointment.get_upcoming_for_patient(self.patient_id)
        self.assertEqual(len(upcoming), 0)

    def test_appointments_sorted_soonest_first(self):
        in_5_days = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        in_1_day = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        Appointment("appt_later", self.patient_id, "clinic1",
                    in_5_days, "09:00", "Later appointment").save()
        Appointment("appt_sooner", self.patient_id, "clinic1",
                    in_1_day, "09:00", "Sooner appointment").save()

        upcoming = Appointment.get_upcoming_for_patient(self.patient_id)
        # The soonest one (appt_sooner) should be first in the list.
        self.assertEqual(upcoming[0][0], "appt_sooner")
        self.assertEqual(upcoming[1][0], "appt_later")

    def test_other_patients_appointments_not_included(self):
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        Appointment("appt_other", "99999999", "clinic1",
                    tomorrow, "09:00", "Someone else's appointment").save()

        upcoming = Appointment.get_upcoming_for_patient(self.patient_id)
        self.assertEqual(len(upcoming), 0)

    def tearDown(self):
        path = os.path.join(TEST_DATA_DIR, "appointments.json")
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
