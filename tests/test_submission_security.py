"""
Unit tests for the /submit_task route's security and resubmission rules.

Covers:
- A patient cannot submit a file to a task not assigned to them.
- A patient CAN submit to their own task.
- Resubmission is allowed while status is Pending / Needs Follow-up.
- Resubmission is BLOCKED once status is Reviewed - Normal / Escalated.

These use Flask's test client to exercise the real route end to end,
rather than testing the underlying functions in isolation - this is
important because the authorisation check lives in the route itself.
"""

import unittest
import json
import os
import io

from app import app
from models.health_task import HealthTask

DATA_DIR = "data"


class TestSubmissionSecurity(unittest.TestCase):

    def setUp(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        # Start every test with clean, empty data files. appointments.json
        # is required too - the dashboard route (which submit_task
        # redirects to) reads it to build the "upcoming appointments"
        # section, so it must exist even though these tests don't
        # exercise appointments directly.
        for filename in ["users.json", "health_tasks.json", "task_submissions.json",
                          "appointments.json"]:
            with open(os.path.join(DATA_DIR, filename), "w") as f:
                json.dump({}, f)

        app.config["TESTING"] = True
        self.client = app.test_client()

        # Two patients: the rightful owner of the task, and an intruder.
        self.client.post("/register", data={
            "role": "patient", "user_id": "11112024", "name": "Owner",
            "email": "owner@example.com", "password": "Str0ng!Pass",
        })
        self.client.post("/register", data={
            "role": "patient", "user_id": "22222024", "name": "Intruder",
            "email": "intruder@example.com", "password": "Str0ng!Pass",
        })

        # A task assigned ONLY to the owner.
        task = HealthTask("task_secure1", "Private task", "desc",
                           "2030-01-01", "clinic1", "11112024")
        task.save()

    def test_unauthorised_patient_cannot_submit(self):
        intruder = app.test_client()
        intruder.post("/login", data={"user_id": "22222024", "password": "Str0ng!Pass"})

        response = intruder.post("/submit_task/task_secure1", data={
            "submission_file": (io.BytesIO(b"date,reading\n2026-01-01,x"), "sneaky.csv"),
        }, content_type="multipart/form-data", follow_redirects=True)

        body = response.get_data(as_text=True)
        self.assertIn("not assigned to you", body)

        # Confirm no submission record was actually created.
        with open(os.path.join(DATA_DIR, "task_submissions.json")) as f:
            submissions = json.load(f)
        self.assertNotIn("22222024_task_secure1", submissions)

    def test_rightful_owner_can_submit(self):
        owner = app.test_client()
        owner.post("/login", data={"user_id": "11112024", "password": "Str0ng!Pass"})

        response = owner.post("/submit_task/task_secure1", data={
            "submission_file": (io.BytesIO(b"date,reading\n2026-01-01,120/80"), "real.csv"),
        }, content_type="multipart/form-data", follow_redirects=True)

        body = response.get_data(as_text=True)
        self.assertIn("submitted successfully", body)

    def test_resubmission_allowed_while_pending(self):
        owner = app.test_client()
        owner.post("/login", data={"user_id": "11112024", "password": "Str0ng!Pass"})
        owner.post("/submit_task/task_secure1", data={
            "submission_file": (io.BytesIO(b"first"), "first.csv"),
        }, content_type="multipart/form-data")

        # Second submission while still Pending should succeed.
        response = owner.post("/submit_task/task_secure1", data={
            "submission_file": (io.BytesIO(b"second"), "second.csv"),
        }, content_type="multipart/form-data", follow_redirects=True)

        body = response.get_data(as_text=True)
        self.assertIn("submitted successfully", body)

    def test_resubmission_blocked_after_review_completed(self):
        owner = app.test_client()
        owner.post("/login", data={"user_id": "11112024", "password": "Str0ng!Pass"})
        owner.post("/submit_task/task_secure1", data={
            "submission_file": (io.BytesIO(b"first"), "first.csv"),
        }, content_type="multipart/form-data")

        # Simulate a clinician having completed their review.
        with open(os.path.join(DATA_DIR, "task_submissions.json")) as f:
            submissions = json.load(f)
        submissions["11112024_task_secure1"]["review_status"] = "Reviewed - Normal"
        with open(os.path.join(DATA_DIR, "task_submissions.json"), "w") as f:
            json.dump(submissions, f)

        response = owner.post("/submit_task/task_secure1", data={
            "submission_file": (io.BytesIO(b"too late"), "toolate.csv"),
        }, content_type="multipart/form-data", follow_redirects=True)

        body = response.get_data(as_text=True)
        self.assertIn("already been reviewed", body)

    def test_submitting_to_nonexistent_task_is_rejected(self):
        owner = app.test_client()
        owner.post("/login", data={"user_id": "11112024", "password": "Str0ng!Pass"})

        response = owner.post("/submit_task/task_does_not_exist", data={
            "submission_file": (io.BytesIO(b"data"), "file.csv"),
        }, content_type="multipart/form-data", follow_redirects=True)

        body = response.get_data(as_text=True)
        self.assertIn("could not be found", body)

    def tearDown(self):
        for filename in ["users.json", "health_tasks.json", "task_submissions.json"]:
            path = os.path.join(DATA_DIR, filename)
            if os.path.exists(path):
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
