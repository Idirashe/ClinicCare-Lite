"""
Integration tests for the automated form-completeness checking wired
into /submit_task (Section D of the project brief).
"""

import unittest
import json
import os
import io

from app import app
from models.health_task import HealthTask

DATA_DIR = "data"


class TestFormCompletenessIntegration(unittest.TestCase):

    def setUp(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        for filename in ["users.json", "health_tasks.json", "task_submissions.json",
                          "appointments.json"]:
            with open(os.path.join(DATA_DIR, filename), "w") as f:
                json.dump({}, f)

        app.config["TESTING"] = True
        self.client = app.test_client()

        self.client.post("/register", data={
            "role": "patient", "user_id": "12122024", "name": "Form Test",
            "email": "form@example.com", "password": "Str0ng!Pass",
        })
        self.client.post("/login", data={"user_id": "12122024", "password": "Str0ng!Pass"})

        task = HealthTask(
            "task_form1", "Blood pressure log", "desc", "2030-01-01", "clinic1",
            "12122024",
            required_fields=["date", "reading"],
            field_types={"date": "date", "reading": "number"},
        )
        task.save()

    def _submit_csv(self, content_bytes, filename="data.csv"):
        return self.client.post("/submit_task/task_form1", data={
            "submission_file": (io.BytesIO(content_bytes), filename),
        }, content_type="multipart/form-data", follow_redirects=True)

    def test_missing_required_column_is_reported(self):
        response = self._submit_csv(b"date\n2026-01-01\n")
        body = response.get_data(as_text=True)
        self.assertIn("Form check", body)
        self.assertIn("reading", body)
        self.assertIn("missing", body)

    def test_empty_required_field_is_reported(self):
        response = self._submit_csv(b"date,reading\n2026-01-01,\n")
        body = response.get_data(as_text=True)
        self.assertIn("Form check", body)
        self.assertIn("missing a value", body)

    def test_invalid_date_format_is_reported(self):
        response = self._submit_csv(b"date,reading\nnot-a-date,120\n")
        body = response.get_data(as_text=True)
        self.assertIn("Form check", body)
        self.assertIn("should be a date", body)

    def test_invalid_number_format_is_reported(self):
        response = self._submit_csv(b"date,reading\n2026-01-01,not-a-number\n")
        body = response.get_data(as_text=True)
        self.assertIn("Form check", body)
        self.assertIn("should be a number", body)

    def test_valid_submission_passes_with_no_complaints(self):
        response = self._submit_csv(b"date,reading\n2026-01-01,120\n")
        body = response.get_data(as_text=True)
        self.assertIn("passed the completeness check", body)
        self.assertNotIn("Form check", body)

    def test_checker_never_comments_on_clinical_meaning(self):
        import re

        response = self._submit_csv(b"date,reading\n2026-01-01,240\n")
        body = response.get_data(as_text=True).lower()
        self.assertIn("passed the completeness check", body)

        forbidden_words = ["dangerous", "abnormal", "concerning"]
        for word in forbidden_words:
            pattern = r"\b" + re.escape(word) + r"\b"
            self.assertIsNone(
                re.search(pattern, body),
                f"Found forbidden clinical-judgement word: '{word}'"
            )

    def tearDown(self):
        for filename in ["users.json", "health_tasks.json", "task_submissions.json"]:
            path = os.path.join(DATA_DIR, filename)
            if os.path.exists(path):
                os.remove(path)


if __name__ == "__main__":
    unittest.main()